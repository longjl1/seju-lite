from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from seju_lite.agent.base import BaseAgent
from seju_lite.bus.events import InboundMessage

logger = logging.getLogger("seju_lite.agent.orchestrator")


@dataclass
class ExecutionContext:
    """Typed execution metadata passed from workflow layer to agents."""

    selected_agent: str
    workflow_plan: list[str] = field(default_factory=list)
    planner_source: str = "rule"
    planner_confidence: float = 1.0
    planner_reason: str = "keyword_router"
    extras: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected_agent": self.selected_agent,
            "workflow_plan": self.workflow_plan,
            "planner_source": self.planner_source,
            "planner_confidence": self.planner_confidence,
            "planner_reason": self.planner_reason,
            **self.extras,
        }


class AgentOrchestrator:
    """Execute requests on selected agents, with lightweight routing compatibility."""

    def __init__(
        self,
        *,
        agents: dict[str, BaseAgent],
        mode: str = "single",
        default_agent: str = "main",
        routing: dict[str, list[str]] | None = None,
        before_dispatch: Callable[[str, InboundMessage, dict[str, Any]], None] | None = None,
        after_dispatch: Callable[[str, InboundMessage, dict[str, Any], float, str], None] | None = None,
    ):
        if default_agent not in agents:
            raise ValueError(f"default_agent '{default_agent}' not found in registry")

        self._agents = agents
        self._mode = (mode or "single").strip().lower()
        self._default = default_agent
        self._routing = routing or {}
        self._before_dispatch = before_dispatch
        self._after_dispatch = after_dispatch

    async def handle(self, inbound: InboundMessage) -> str:
        # Legacy one-step entrypoint. Preferred path is WorkflowOrchestrator.
        agent_name = self.route_by_rules(inbound.content)
        return await self.dispatch(agent_name, inbound)

    @property
    def available_agents(self) -> set[str]:
        return set(self._agents.keys())

    def has_agent(self, name: str) -> bool:
        return name in self._agents

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def default_agent(self) -> str:
        return self._default

    def route_by_rules(self, content: str) -> str:
        return self._select_agent(content)

    async def dispatch(
        self,
        agent_name: str,
        inbound: InboundMessage,
        context: ExecutionContext | dict[str, Any] | None = None,
    ) -> str:
        started_perf = time.perf_counter()
        agent = self._agents.get(agent_name) or self._agents[self._default]
        if isinstance(context, ExecutionContext):
            payload = context.to_dict()
        else:
            payload = dict(context or {})
        payload["selected_agent"] = agent.name

        logger.info(
            "Task started: mode=%s selected_agent=%s default=%s channel=%s chat_id=%s",
            self._mode,
            agent.name,
            self._default,
            inbound.channel,
            inbound.chat_id,
        )
        if self._before_dispatch is not None:
            self._before_dispatch(agent.name, inbound, payload)
        try:
            result = await agent.run(inbound, context=payload)
        except Exception:
            elapsed_s = time.perf_counter() - started_perf
            logger.exception(
                "Task failed: selected_agent=%s elapsed_s=%.1f",
                agent.name,
                elapsed_s,
            )
            raise

        elapsed_s = time.perf_counter() - started_perf
        if self._after_dispatch is not None:
            self._after_dispatch(agent.name, inbound, payload, elapsed_s, result)
        logger.info(
            "Task completed: selected_agent=%s elapsed_s=%.1f",
            agent.name,
            elapsed_s,
        )
        return result

    def _select_agent(self, content: str) -> str:
        if self._mode != "multi":
            return self._default

        text = (content or "").lower()
        if not text.strip():
            return self._default

        for agent_name, keywords in self._routing.items():
            if agent_name not in self._agents:
                continue
            for kw in keywords:
                token = (kw or "").strip().lower()
                if token and token in text:
                    return agent_name

        return self._default
