"""Subagent manager for background task execution in seju-lite."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any

from seju_lite.bus.events import OutboundMessage
from seju_lite.tools.registry import ToolRegistry


class SubagentManager:
    """Manage async subagent tasks and send one response per completed task."""

    def __init__(
        self,
        provider,
        bus,
        tools: ToolRegistry,
        max_iterations: int = 10,
    ):
        self.provider = provider
        self.bus = bus
        self.tools = tools
        self.max_iterations = max_iterations

        self._logger = logging.getLogger("seju_lite.subagent")
        self._running_tasks: dict[str, asyncio.Task[None]] = {}
        self._session_tasks: dict[str, set[str]] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def _to_openai_tool_call_dict(tc) -> dict[str, Any]:
        return {
            "id": tc.id,
            "type": "function",
            "function": {
                "name": tc.name,
                "arguments": json.dumps(tc.arguments, ensure_ascii=False),
            },
        }

    def _subagent_tool_defs(self) -> list[dict[str, Any]]:
        defs = self.tools.get_definitions()
        out = []
        for item in defs:
            fn = item.get("function", {})
            # prevent recursive spawning
            if fn.get("name") == "spawn":
                continue
            out.append(item)
        return out

    async def spawn(
        self,
        task: str,
        label: str | None = None,
        origin_channel: str = "cli",
        origin_chat_id: str = "local",
        session_key: str | None = None,
    ) -> str:
        if not session_key:
            session_key = f"{origin_channel}:{origin_chat_id}"

        task_id = str(uuid.uuid4())[:8]
        display_label = label or (task[:30] + ("..." if len(task) > 30 else ""))

        bg_task = asyncio.create_task(
            self._run_subagent(
                task_id=task_id,
                task=task,
                label=display_label,
                origin_channel=origin_channel,
                origin_chat_id=origin_chat_id,
            )
        )

        async with self._lock:
            self._running_tasks[task_id] = bg_task
            self._session_tasks.setdefault(session_key, set()).add(task_id)

        def _cleanup(_: asyncio.Task) -> None:
            self._running_tasks.pop(task_id, None)
            if session_key in self._session_tasks:
                self._session_tasks[session_key].discard(task_id)
                if not self._session_tasks[session_key]:
                    del self._session_tasks[session_key]

        bg_task.add_done_callback(_cleanup)

        self._logger.info("Spawned subagent [%s]: %s", task_id, display_label)
        return f"Subagent [{display_label}] started (id: {task_id}). I will notify when it completes."

    async def _run_subagent(
        self,
        task_id: str,
        task: str,
        label: str,
        origin_channel: str,
        origin_chat_id: str,
    ) -> None:
        self._logger.info("Subagent [%s] starting task: %s", task_id, label)

        try:
            messages: list[dict[str, Any]] = [
                {
                    "role": "system",
                    "content": (
                        "You are a focused subagent for a single delegated task. "
                        "Use tools when needed. Do not claim success unless tool results confirm it."
                    ),
                },
                {"role": "user", "content": task},
            ]
            final_result: str | None = None

            for _ in range(self.max_iterations):
                response = await self.provider.generate(
                    messages=messages,
                    tools=self._subagent_tool_defs(),
                )

                if response.has_tool_calls:
                    tool_calls = [self._to_openai_tool_call_dict(tc) for tc in response.tool_calls]
                    messages.append(
                        {
                            "role": "assistant",
                            "content": response.content,
                            "tool_calls": tool_calls,
                        }
                    )

                    for tc in response.tool_calls:
                        if tc.name == "spawn":
                            result = "Tool 'spawn' is disabled inside subagent execution."
                        else:
                            result = await self.tools.execute(tc.name, tc.arguments)
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tc.id,
                                "name": tc.name,
                                "content": result,
                            }
                        )
                else:
                    if response.content and response.content.strip():
                        final_result = response.content
                        break
                    messages.append(
                        {
                            "role": "user",
                            "content": "Provide a concise final answer based on completed tool results.",
                        }
                    )

            if final_result is None:
                final_result = "Task completed but no final response was generated."

            await self._announce_result(
                task_id=task_id,
                label=label,
                task=task,
                result=final_result,
                origin_channel=origin_channel,
                origin_chat_id=origin_chat_id,
                status="ok",
            )
            self._logger.info("Subagent [%s] completed", task_id)
        except asyncio.CancelledError:
            self._logger.info("Subagent [%s] cancelled", task_id)
            raise
        except Exception as exc:
            self._logger.exception("Subagent [%s] failed", task_id)
            await self._announce_result(
                task_id=task_id,
                label=label,
                task=task,
                result=f"Error: {type(exc).__name__}: {exc}",
                origin_channel=origin_channel,
                origin_chat_id=origin_chat_id,
                status="error",
            )

    async def _announce_result(
        self,
        task_id: str,
        label: str,
        task: str,
        result: str,
        origin_channel: str,
        origin_chat_id: str,
        status: str,
    ) -> None:
        if self.bus is None:
            return

        status_text = "completed successfully" if status == "ok" else "failed"
        content = (
            f"[Subagent '{label}' {status_text}]\n"
            f"Task: {task}\n\n"
            f"Result:\n{result}"
        )

        msg = OutboundMessage(
            channel=origin_channel,
            chat_id=origin_chat_id,
            content=content,
            metadata={"subagent_task_id": task_id},
        )
        await self.bus.publish_outbound(msg)

    async def cancel_by_session(self, session_key: str) -> int:
        task_ids = list(self._session_tasks.get(session_key, set()))
        tasks = [
            self._running_tasks[tid]
            for tid in task_ids
            if tid in self._running_tasks and not self._running_tasks[tid].done()
        ]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        async with self._lock:
            self._session_tasks.pop(session_key, None)
        return len(tasks)

    async def cancel_all(self) -> int:
        tasks = [task for task in self._running_tasks.values() if not task.done()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        async with self._lock:
            self._session_tasks.clear()
        return len(tasks)

    async def close(self) -> None:
        tasks = [t for t in self._running_tasks.values() if not t.done()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        self._running_tasks.clear()
        self._session_tasks.clear()
