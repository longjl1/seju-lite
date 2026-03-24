from __future__ import annotations

import json
import logging

from seju_lite.agent.orchestrator import AgentOrchestrator, ExecutionContext
from seju_lite.bus.events import InboundMessage
from seju_lite.providers.base import LLMProvider

logger = logging.getLogger("seju_lite.agent.workflow")

# 选择 agent -> dispatch
class WorkflowOrchestrator:
    """Workflow entrypoint with optional LLM planner."""

    def __init__(
        self,
        router: AgentOrchestrator,
        provider: LLMProvider | None = None,
        *,
        enable_llm_planner: bool = False,
        planner_confidence_threshold: float = 0.65,
    ):
        self.router = router
        self.provider = provider
        self.enable_llm_planner = enable_llm_planner
        self.planner_confidence_threshold = planner_confidence_threshold

    @staticmethod
    def _extract_json_object(raw: str) -> dict: # 返回json 
        text = (raw or "").strip()
        if not text:
            return {}

        if text.startswith("```"):
            lines = text.splitlines()
            if len(lines) >= 3 and lines[0].startswith("```") and lines[-1].startswith("```"):
                text = "\n".join(lines[1:-1]).strip()
            if text.lower().startswith("json"):
                text = text[4:].strip()

        try:
            parsed = json.loads(text)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                try:
                    parsed = json.loads(text[start : end + 1])
                    return parsed if isinstance(parsed, dict) else {}
                except json.JSONDecodeError:
                    return {}
            return {}

    # 
    async def _plan_agent_with_llm(self, inbound: InboundMessage) -> tuple[str | None, float, str]:
        if not self.provider:
            return None, 0.0, "provider_unavailable"

        planner_messages = [
            {
                "role": "system",
                "content": (
                    "You are a strict workflow planner.\n"
                    "Choose exactly one agent for the request.\n"
                    "Available agents: main, local, web.\n"
                    "- local: local tasks, file/memory/session handling, non-web operations.\n"
                    "- web: web browsing/fetch and external internet-heavy tasks.\n"
                    "- main: general fallback.\n"
                    "Respond with JSON only, no markdown:\n"
                    '{"agent":"main|local|web","confidence":0.0,"reason":"short"}'
                ),
            },
            {"role": "user", "content": inbound.content},
        ]
        # 询问llm
        response = await self.provider.generate(messages=planner_messages, tools=None)
        parsed = self._extract_json_object(response.content or "") # JSON result
        candidate = str(parsed.get("agent", "")).strip()
        confidence = parsed.get("confidence", 0.0)
        reason = str(parsed.get("reason", "")).strip() or "no_reason"

        try:
            confidence_f = float(confidence)
        except (TypeError, ValueError):
            confidence_f = 0.0

        if not candidate or not self.router.has_agent(candidate):
            return None, confidence_f, f"invalid_agent:{candidate or 'empty'}"
        if confidence_f < self.planner_confidence_threshold:
            return None, confidence_f, f"low_confidence:{confidence_f:.2f}"
        return candidate, confidence_f, reason

    async def handle(self, inbound: InboundMessage) -> str:
        agent_name = self.router.route_by_rules(inbound.content)
        planner_source = "rule"
        planner_reason = "keyword_router"
        planner_confidence = 1.0

        if self.enable_llm_planner and self.router.mode == "multi":
            try:
                planned_agent, confidence, reason = await self._plan_agent_with_llm(inbound)
            except Exception:
                planned_agent, confidence, reason = None, 0.0, "planner_error"
                logger.exception("LLM planner failed; fallback to keyword router")

            if planned_agent:
                agent_name = planned_agent
                planner_source = "llm"
                planner_reason = reason
                planner_confidence = confidence
            else:
                planner_source = "rule_fallback"
                planner_reason = reason
                planner_confidence = confidence

        logger.info(
            "Workflow route selected: source=%s agent=%s confidence=%.2f reason=%s",
            planner_source,
            agent_name,
            planner_confidence,
            planner_reason,
        )
        return await self.router.dispatch(
            agent_name,
            inbound,
            context=ExecutionContext(
                selected_agent=agent_name,
                workflow_plan=[agent_name],
                planner_source=planner_source,
                planner_confidence=planner_confidence,
                planner_reason=planner_reason,
            ),
        )
