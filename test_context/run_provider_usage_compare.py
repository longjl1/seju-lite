from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from seju_lite.agent.context_policy import ContextPolicyDecider
from seju_lite.agent.context_utils import filter_low_signal_history
from seju_lite.agent.v2.runtime_adapter import RuntimeAdapterConfigV2, RuntimeContextAdapterV2
from seju_lite.config.loader import load_config
from seju_lite.providers.base import LLMResponse, ToolCall
from seju_lite.session.manager import SessionManager

console = Console()


@dataclass
class UsageCall:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class UsageTrackingOpenAICompatibleProvider:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.calls: list[UsageCall] = []
        client_kwargs = {
            "timeout": httpx.Timeout(60, connect=10),
            "limits": httpx.Limits(max_connections=10, max_keepalive_connections=5, keepalive_expiry=30),
            "http2": True,
        }
        try:
            self._client = httpx.AsyncClient(**client_kwargs)
        except ImportError:
            client_kwargs["http2"] = False
            self._client = httpx.AsyncClient(**client_kwargs)

    @staticmethod
    def _parse_tool_arguments(raw_args: Any) -> dict[str, Any]:
        if isinstance(raw_args, dict):
            return raw_args
        if isinstance(raw_args, str):
            try:
                parsed = json.loads(raw_args)
                return parsed if isinstance(parsed, dict) else {}
            except json.JSONDecodeError:
                return {}
        return {}

    def reset_usage(self) -> None:
        self.calls = []

    async def generate(self, messages: list[dict], tools: list[dict] | None = None) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        response = await self._client.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

        usage = data.get("usage") or {}
        self.calls.append(
            UsageCall(
                prompt_tokens=int(usage.get("prompt_tokens") or 0),
                completion_tokens=int(usage.get("completion_tokens") or 0),
                total_tokens=int(usage.get("total_tokens") or 0),
            )
        )

        msg = data["choices"][0]["message"]
        tool_calls: list[ToolCall] = []
        for tc in msg.get("tool_calls", []) or []:
            fn = tc.get("function") or {}
            name = fn.get("name")
            if not name:
                continue
            tool_calls.append(
                ToolCall(
                    id=tc.get("id") or f"tracked_call_{len(tool_calls)}",
                    name=name,
                    arguments=self._parse_tool_arguments(fn.get("arguments", {})),
                )
            )
        return LLMResponse(
            content=msg.get("content"),
            tool_calls=tool_calls,
            finish_reason=data["choices"][0].get("finish_reason", "stop"),
        )

    async def close(self) -> None:
        await self._client.aclose()


def _resolve_case_workspace(case_dir: Path | None, fallback_workspace: Path) -> Path:
    if case_dir is None:
        return fallback_workspace
    return (case_dir / "workspace").resolve()


def _build_messages_for_mode(
    *,
    workspace: Path,
    system_prompt: str,
    provider: UsageTrackingOpenAICompatibleProvider,
    session,
    current_message: str,
    max_history: int,
    include_memory: bool,
    include_skills: bool,
    mode: str,
    summary_trigger_messages: int,
    summary_keep_recent_messages: int,
    summary_max_messages_to_summarize: int,
    force_history: bool,
):
    async def _inner():
        policy = ContextPolicyDecider(default_history_limit=max_history).decide(current_message)
        if force_history:
            raw_history = session.get_history(max_history)
            effective_include_memory = include_memory
            effective_include_skills = include_skills
        else:
            raw_history = session.get_history(policy.history_limit) if policy.include_history else []
            effective_include_memory = include_memory and policy.include_memory
            effective_include_skills = include_skills and policy.include_skills

        history = filter_low_signal_history(raw_history)
        adapter = RuntimeContextAdapterV2(
            workspace=workspace,
            system_prompt=system_prompt,
            config=RuntimeAdapterConfigV2(
                mode=mode,
                include_memory=effective_include_memory,
                llm_summary_trigger_messages=summary_trigger_messages,
                llm_summary_keep_recent_messages=summary_keep_recent_messages,
                llm_summary_max_messages_to_summarize=summary_max_messages_to_summarize,
            ),
        )
        messages = await adapter.build_messages(
            history=history,
            current_message=current_message,
            provider=provider,
            channel="test",
            chat_id="context-usage-test",
            metadata=session.metadata,
            include_memory=effective_include_memory,
            include_skills=effective_include_skills,
        )
        return history, messages

    return _inner()


async def main() -> None:
    parser = argparse.ArgumentParser(description="Compare official provider usage for old and v2 context modes.")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--case-dir", default=None)
    parser.add_argument("--session", required=True)
    parser.add_argument("--message", required=True)
    parser.add_argument("--with-llm-summary", action="store_true")
    parser.add_argument("--force-history", action="store_true")
    parser.add_argument("--max-output-tokens", type=int, default=16)  # 输出可以压低一点
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    load_dotenv(config_path.with_name(".env"), override=False)
    load_dotenv(override=False)
    config = load_config(config_path)
    workspace = _resolve_case_workspace(
        Path(args.case_dir).resolve() if args.case_dir else None,
        Path(config.agent.workspace).resolve(),
    )

    if config.provider.kind not in {"deepseek", "openai_compatible"}:
        raise SystemExit("Official usage comparison currently supports deepseek/openai_compatible only.")

    base_url = (config.provider.apiBase or "").strip() or "https://api.deepseek.com"
    provider = UsageTrackingOpenAICompatibleProvider(
        base_url=base_url,
        api_key=config.provider.apiKey,
        model=config.provider.model,
        temperature=config.provider.temperature,
        max_tokens=args.max_output_tokens,
    )

    try:
        sessions = SessionManager(workspace / "sessions")
        session = sessions.get_or_create(args.session)
        modes = ["old", "v2_trim"]
        if args.with_llm_summary:
            modes.append("v2_llm_summary")

        rows: list[dict[str, Any]] = []
        for mode in modes:
            provider.reset_usage()
            history, messages = await _build_messages_for_mode(
                workspace=workspace,
                system_prompt=config.agent.systemPrompt,
                provider=provider,
                session=session,
                current_message=args.message,
                max_history=config.agent.maxHistory,
                include_memory=config.agent.enableMemory,
                include_skills=config.agent.enableSkills,
                mode=mode,
                summary_trigger_messages=config.agent.v2SummaryTriggerMessages,
                summary_keep_recent_messages=config.agent.v2SummaryKeepRecentMessages,
                summary_max_messages_to_summarize=config.agent.v2SummaryMaxMessagesToSummarize,
                force_history=args.force_history,
            )
            await provider.generate(messages=messages, tools=None)
            prompt_tokens = sum(item.prompt_tokens for item in provider.calls)
            completion_tokens = sum(item.completion_tokens for item in provider.calls)
            total_tokens = sum(item.total_tokens for item in provider.calls)
            rows.append(
                {
                    "mode": mode,
                    "history": len(history),
                    "messages": len(messages),
                    "api_calls": len(provider.calls),
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                }
            )

        baseline = next((row for row in rows if row["mode"] == "old"), None)
        table = Table(title="Official Provider Usage Comparison")
        table.add_column("Mode")
        table.add_column("History")
        table.add_column("Msgs")
        table.add_column("API Calls")
        table.add_column("Prompt", justify="right")
        table.add_column("Completion", justify="right")
        table.add_column("Total", justify="right")
        table.add_column("Delta vs old", justify="right")

        for row in rows:
            delta = "-"
            if baseline is not None:
                delta = f"{row['total_tokens'] - baseline['total_tokens']:+d}"
            table.add_row(
                row["mode"],
                str(row["history"]),
                str(row["messages"]),
                str(row["api_calls"]),
                str(row["prompt_tokens"]),
                str(row["completion_tokens"]),
                str(row["total_tokens"]),
                delta,
            )

        console.print(table)
        console.print(
            f"[dim]Workspace: {workspace} | Session: {args.session} | Message: {args.message}[/dim]"
        )
    finally:
        await provider.close()


if __name__ == "__main__":
    asyncio.run(main())
