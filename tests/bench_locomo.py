from __future__ import annotations

import argparse
import asyncio
import copy
import json
import re
import string
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from seju_lite.bus.events import InboundMessage
from seju_lite.runtime.app import create_app
from seju_lite.runtime.runner import close_app

try:
    from nltk.stem import PorterStemmer

    _STEMMER = PorterStemmer()
except Exception:  # pragma: no cover - optional dependency in some envs
    _STEMMER = None


CATEGORY_NAME = {
    1: "multi_hop",
    2: "temporal",
    3: "open_domain",
    4: "single_hop",
    5: "adversarial",
}


def normalize_answer(text: str) -> str:
    text = str(text).replace(",", "")
    text = text.lower()
    text = "".join(ch for ch in text if ch not in set(string.punctuation))
    text = re.sub(r"\b(a|an|the|and)\b", " ", text)
    return " ".join(text.split())


def _stem_tokens(tokens: list[str]) -> list[str]:
    if _STEMMER is None:
        return tokens
    return [_STEMMER.stem(t) for t in tokens]


def f1_score(prediction: str, ground_truth: str) -> float:
    pred_tokens = _stem_tokens(normalize_answer(prediction).split())
    gold_tokens = _stem_tokens(normalize_answer(ground_truth).split())

    if not pred_tokens or not gold_tokens:
        return 0.0

    common = Counter(pred_tokens) & Counter(gold_tokens)
    num_same = sum(common.values())
    if num_same == 0:
        return 0.0

    precision = num_same / len(pred_tokens)
    recall = num_same / len(gold_tokens)
    return (2 * precision * recall) / (precision + recall)


def f1_multi_answer(prediction: str, ground_truth: str) -> float:
    """Official-style category-1 scoring from LoCoMo evaluation.py."""
    predictions = [p.strip() for p in str(prediction).split(",") if p.strip()]
    ground_truths = [g.strip() for g in str(ground_truth).split(",") if g.strip()]

    if not predictions or not ground_truths:
        return 0.0

    per_gt = []
    for gt in ground_truths:
        per_gt.append(max(f1_score(p, gt) for p in predictions))
    return sum(per_gt) / len(per_gt)


def score_locomo(prediction: str, answer: str, category: int) -> float:
    """
    Mirror LoCoMo task_eval/evaluation.py::eval_question_answering:
    - cat 1: multi-answer F1
    - cat 2/3/4: single-answer token F1
    - cat 5: adversarial yes/no style rule
    """
    pred = str(prediction)
    gold = str(answer)

    if category == 3:
        gold = gold.split(";")[0].strip()

    if category in (2, 3, 4):
        return f1_score(pred, gold)
    if category == 1:
        return f1_multi_answer(pred, gold)
    if category == 5:
        lowered = pred.lower()
        return 1.0 if ("no information available" in lowered or "not mentioned" in lowered) else 0.0

    return f1_score(pred, gold)


def iter_sessions(conversation: dict[str, Any]) -> list[tuple[int, str, list[dict[str, Any]]]]:
    pairs: list[tuple[int, str, list[dict[str, Any]]]] = []
    for key, value in conversation.items():
        m = re.fullmatch(r"session_(\d+)", key)
        if m and isinstance(value, list):
            pairs.append((int(m.group(1)), key, value))
    pairs.sort(key=lambda x: x[0])
    return pairs


def _format_turn(turn: dict[str, Any]) -> str:
    """Align with LoCoMo prompting style in task_eval/gpt_utils.py."""
    speaker = turn.get("speaker", "Unknown")
    text = (turn.get("text") or "").strip()
    dia_id = turn.get("dia_id")

    base = f'{speaker} said, "{text}"'
    if turn.get("blip_caption"):
        base += f" and shared {turn['blip_caption']}"
    if dia_id:
        base += f" [{dia_id}]"
    return base


def seed_session_history(agent, sample: dict[str, Any], session_key: str) -> list[dict[str, Any]]:
    """
    Put LoCoMo conversation into seju-lite short-term history.
    Include DATE markers to support temporal QA (cat 2).
    """
    session = agent.sessions.get_or_create(session_key)
    session.messages = []

    conversation = sample.get("conversation", {})
    speaker_a = conversation.get("speaker_a")

    for sess_num, sess_name, turns in iter_sessions(conversation):
        date_key = f"session_{sess_num}_date_time"
        date_text = str(conversation.get(date_key, "")).strip()
        if date_text:
            session.messages.append({"role": "user", "content": f"DATE: {date_text}"})

        for turn in turns:
            formatted = _format_turn(turn)
            if not formatted:
                continue
            role = "user" if turn.get("speaker") == speaker_a else "assistant"
            session.messages.append({"role": role, "content": formatted})

    agent.sessions.save(session)
    return copy.deepcopy(session.messages)


def build_question_prompt(question: str, category: int, answer: str, qa_index: int) -> tuple[str, dict[str, str] | None]:
    """Follow LoCoMo task_eval/gpt_utils.py question shaping."""
    q = question.strip()

    if category == 2:
        return q + " Use DATE of CONVERSATION to answer with an approximate date.", None

    if category == 5:
        # Deterministic variant of official A/B option generation.
        if qa_index % 2 == 0:
            options = {
                "a": "Not mentioned in the conversation",
                "b": str(answer),
            }
        else:
            options = {
                "a": str(answer),
                "b": "Not mentioned in the conversation",
            }
        prompt = q + f" Select the correct answer: (a) {options['a']} (b) {options['b']}."
        return prompt, options

    return q, None


def decode_cat5_prediction(prediction: str, options: dict[str, str]) -> str:
    pred = prediction.strip().lower()
    if len(pred) == 1:
        if "a" in pred:
            return options["a"]
        return options["b"]
    if "(a)" in pred:
        return options["a"]
    if "(b)" in pred:
        return options["b"]
    return prediction


async def ask_question(agent, session_key: str, question: str) -> str:
    inbound = InboundMessage(
        channel="locomo",
        sender_id="benchmark",
        chat_id=session_key,
        content=question,
        metadata={},
    )
    return await agent.process_message(inbound)


async def run_benchmark(
    config_path: Path,
    dataset_path: Path,
    max_samples: int | None,
    max_qa_per_sample: int | None,
) -> dict[str, Any]:
    samples = json.loads(dataset_path.read_text(encoding="utf-8"))
    if not isinstance(samples, list):
        raise ValueError("LoCoMo dataset file must be a JSON list.")

    if max_samples is not None:
        samples = samples[:max_samples]

    app = await create_app(config_path)
    results: list[dict[str, Any]] = []
    per_category_scores: dict[str, list[float]] = defaultdict(list)

    try:
        for sample in samples:
            sample_id = sample.get("sample_id", "unknown")
            session_key = f"locomo:{sample_id}"
            base_history = seed_session_history(app.agent, sample, session_key)

            qa_items = sample.get("qa", [])
            if max_qa_per_sample is not None:
                qa_items = qa_items[:max_qa_per_sample]

            for idx, qa in enumerate(qa_items, start=1):
                session = app.agent.sessions.get_or_create(session_key)
                session.messages = copy.deepcopy(base_history)
                app.agent.sessions.save(session)

                question = str(qa.get("question", "")).strip()
                answer = str(qa.get("answer", "")).strip()
                category = int(qa.get("category", -1))
                evidence = qa.get("evidence", [])

                if not question:
                    continue

                prompt, cat5_options = build_question_prompt(question, category, answer, idx)
                pred = await ask_question(app.agent, session_key=session_key, question=prompt)

                scored_pred = decode_cat5_prediction(pred, cat5_options) if cat5_options else pred
                locomo_f1 = score_locomo(scored_pred, answer, category)

                category_key = CATEGORY_NAME.get(category, f"cat_{category}")
                per_category_scores[category_key].append(locomo_f1)
                results.append(
                    {
                        "sample_id": sample_id,
                        "qa_index": idx,
                        "category_id": category,
                        "category": category_key,
                        "question": question,
                        "prompt_used": prompt,
                        "gold_answer": answer,
                        "pred_answer_raw": pred,
                        "pred_answer_scored": scored_pred,
                        "locomo_f1": locomo_f1,
                        "evidence": evidence,
                    }
                )
    finally:
        await close_app(app)

    overall_f1 = sum(r["locomo_f1"] for r in results) / len(results) if results else 0.0

    category_summary: dict[str, dict[str, float | int]] = {}
    for cat, scores in per_category_scores.items():
        category_summary[cat] = {
            "count": len(scores),
            "locomo_f1": sum(scores) / len(scores) if scores else 0.0,
        }

    return {
        "meta": {
            "config_path": str(config_path),
            "dataset_path": str(dataset_path),
            "num_samples": len(samples),
            "num_questions": len(results),
            "scoring": "LoCoMo task_eval/evaluation.py compatible category-wise F1",
        },
        "summary": {
            "overall_locomo_f1": overall_f1,
            "by_category": category_summary,
        },
        "results": results,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate seju-lite on LoCoMo QA task.")
    parser.add_argument("--config", default="config.json", help="Path to seju-lite config file.")
    parser.add_argument(
        "--dataset",
        required=True,
        help="Path to LoCoMo dataset JSON (e.g. locomo10.json).",
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=None,
        help="Optional cap on number of conversation samples.",
    )
    parser.add_argument(
        "--max-qa",
        type=int,
        default=None,
        help="Optional cap on QA items per sample.",
    )
    parser.add_argument(
        "--output",
        default="workspace/locomo_eval_results.json",
        help="Output JSON path for detailed benchmark results.",
    )
    return parser.parse_args()


async def _main() -> None:
    args = parse_args()
    report = await run_benchmark(
        config_path=Path(args.config),
        dataset_path=Path(args.dataset),
        max_samples=args.max_samples,
        max_qa_per_sample=args.max_qa,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = report["summary"]
    print("LoCoMo QA benchmark finished.")
    print(f"Questions: {report['meta']['num_questions']}")
    print(f"Overall LoCoMo-F1: {summary['overall_locomo_f1']:.4f}")
    print(f"Saved: {output_path.resolve()}")


if __name__ == "__main__":
    asyncio.run(_main())
