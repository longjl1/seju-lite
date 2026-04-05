from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from seju_lite.bus.events import InboundMessage
from seju_lite.providers.base import LLMProvider
from seju_lite.runtime.scheduler import ScheduledJob, Scheduler

logger = logging.getLogger("seju_lite.schedules")


class ScheduleTask(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    name: str
    prompt: str = Field(min_length=1)
    every_seconds: int = Field(gt=0)
    channel: str = Field(default="web", min_length=1)
    chat_id: str = Field(min_length=1)
    user_id: str = Field(default="web-user", min_length=1)
    enabled: bool = True
    run_immediately: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    last_run_at: str | None = None
    last_result: str | None = None


class ScheduleParseResult(BaseModel):
    name: str
    prompt: str
    every_seconds: int = Field(gt=0)
    run_immediately: bool = False


class ScheduleStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load_all(self) -> list[ScheduleTask]:
        if not self.path.exists():
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            logger.exception("Failed to read schedule store: %s", self.path)
            return []

        if not isinstance(raw, list):
            return []

        items: list[ScheduleTask] = []
        for value in raw:
            try:
                items.append(ScheduleTask.model_validate(value))
            except Exception:
                logger.warning("Skipping invalid schedule task payload")
        return items

    def save_all(self, tasks: list[ScheduleTask]) -> None:
        payload = [task.model_dump() for task in tasks]
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


class ScheduleService:
    def __init__(
        self,
        *,
        provider: LLMProvider | None,
        scheduler: Scheduler,
        store: ScheduleStore,
        run_task_callback,
    ) -> None:
        self.provider = provider
        self.scheduler = scheduler
        self.store = store
        self._run_task_callback = run_task_callback
        self._tasks: dict[str, ScheduleTask] = {}

    @property
    def tasks(self) -> tuple[ScheduleTask, ...]:
        return tuple(sorted(self._tasks.values(), key=lambda item: item.created_at))

    def load(self) -> None:
        self._tasks = {task.id: task for task in self.store.load_all()}
        self._sync_scheduler()

    def list_tasks(self) -> list[ScheduleTask]:
        return list(self.tasks)

    def get_task(self, task_id: str) -> ScheduleTask | None:
        return self._tasks.get(task_id)

    def create_task(self, parsed: ScheduleParseResult, *, channel: str, chat_id: str, user_id: str) -> ScheduleTask:
        task = ScheduleTask(
            name=parsed.name,
            prompt=parsed.prompt,
            every_seconds=parsed.every_seconds,
            run_immediately=parsed.run_immediately,
            channel=channel,
            chat_id=chat_id,
            user_id=user_id,
        )
        if not task.run_immediately:
            task.last_run_at = task.created_at
        self._tasks[task.id] = task
        self._persist()
        self._register_job(task)
        return task

    def delete_task(self, task_id: str) -> bool:
        removed = self._tasks.pop(task_id, None)
        if removed is None:
            return False
        self.scheduler.remove_job(task_id)
        self._persist()
        return True

    async def run_task(self, task_id: str) -> str:
        task = self._tasks.get(task_id)
        if task is None or not task.enabled:
            return "schedule task not available"

        inbound = InboundMessage(
            channel=task.channel,
            sender_id=task.user_id,
            chat_id=task.chat_id,
            content=task.prompt,
            metadata={
                "scheduled_task_id": task.id,
                "scheduled_task_name": task.name,
                "scheduled": True,
            },
        )
        logger.info("Executing schedule task id=%s name=%s", task.id, task.name)
        result = await self._run_task_callback(inbound)
        task.last_run_at = datetime.now(UTC).isoformat()
        task.last_result = result
        task.updated_at = task.last_run_at
        self._persist()
        return result

    async def parse_natural_language(
        self,
        *,
        text: str,
        channel: str,
        chat_id: str,
        user_id: str,
    ) -> ScheduleParseResult:
        parsed = await self._parse_with_llm(text=text, channel=channel, chat_id=chat_id, user_id=user_id)
        if parsed is not None:
            return parsed

        fallback = self._parse_with_rules(text)
        if fallback is not None:
            return fallback
        raise ValueError("Could not parse schedule request")

    async def _parse_with_llm(
        self,
        *,
        text: str,
        channel: str,
        chat_id: str,
        user_id: str,
    ) -> ScheduleParseResult | None:
        if self.provider is None:
            return None

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a strict schedule parser.\n"
                    "Convert the user's request into JSON only.\n"
                    "Support interval schedules only.\n"
                    "Return exactly this schema:\n"
                    '{"name":"short title","prompt":"task prompt","every_seconds":3600,"run_immediately":false}\n'
                    "Rules:\n"
                    "- every_seconds must be a positive integer.\n"
                    "- prompt must describe what the agent should do at runtime.\n"
                    "- name should be short and readable.\n"
                    "- If the user says start now or immediately, set run_immediately=true.\n"
                    "- Do not include markdown."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"channel={channel}\nchat_id={chat_id}\nuser_id={user_id}\n"
                    f"request={text}"
                ),
            },
        ]
        try:
            response = await self.provider.generate(messages=messages, tools=None)
        except Exception:
            logger.exception("LLM schedule parser failed")
            return None

        payload = self._extract_json_object(response.content or "")
        if not payload:
            return None
        try:
            return ScheduleParseResult.model_validate(payload)
        except Exception:
            logger.warning("LLM schedule parser returned invalid payload")
            return None

    @staticmethod
    def _extract_json_object(raw: str) -> dict[str, Any]:
        text = (raw or "").strip()
        if not text:
            return {}
        if text.startswith("```"):
            lines = text.splitlines()
            if len(lines) >= 3:
                text = "\n".join(lines[1:-1]).strip()
            if text.lower().startswith("json"):
                text = text[4:].strip()
        try:
            parsed = json.loads(text)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start < 0 or end <= start:
                return {}
            try:
                parsed = json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return {}
            return parsed if isinstance(parsed, dict) else {}


    ''' if llm parsing fails, try to parse with rules '''
    @staticmethod
    def _parse_with_rules(text: str) -> ScheduleParseResult | None:
        source = (text or "").strip()
        if not source:
            return None

        patterns = [
            (r"每隔\s*(\d+)\s*分钟", 60),
            (r"每隔\s*(\d+)\s*小时", 3600),
            (r"每隔\s*(\d+)\s*天", 86400),
            (r"every\s+(\d+)\s+minutes?", 60),
            (r"every\s+(\d+)\s+hours?", 3600),
            (r"every\s+(\d+)\s+days?", 86400),
        ]
        every_seconds = None
        for pattern, multiplier in patterns:
            match = re.search(pattern, source, flags=re.IGNORECASE)
            if match:
                every_seconds = int(match.group(1)) * multiplier
                break
        if every_seconds is None:
            return None

        prompt = re.sub(r"^(请|帮我|麻烦)\s*", "", source).strip()
        prompt = re.sub(r"(每隔\s*\d+\s*(分钟|小时|天)|every\s+\d+\s+(minutes?|hours?|days?))", "", prompt, flags=re.IGNORECASE).strip(" ，,。.") or source
        run_immediately = bool(re.search(r"(现在|立刻|马上|立即|start now|immediately)", source, flags=re.IGNORECASE))
        name = prompt[:40] if len(prompt) > 40 else prompt
        return ScheduleParseResult(
            name=name or "scheduled task",
            prompt=prompt,
            every_seconds=every_seconds,
            run_immediately=run_immediately,
        )

    def _sync_scheduler(self) -> None:
        existing = {job.name for job in self.scheduler.jobs}
        for job_name in existing:
            self.scheduler.remove_job(job_name)
        for task in self._tasks.values():
            self._register_job(task)

    def _register_job(self, task: ScheduleTask) -> None:
        if not task.enabled:
            return

        job = ScheduledJob(
            name=task.id,
            interval_seconds=task.every_seconds,
            handler=lambda task_id=task.id: self.run_task(task_id),
            run_immediately=task.run_immediately and task.last_run_at is None,
            last_run_at=self._parse_datetime(task.last_run_at),
            metadata={
                "task_name": task.name,
                "channel": task.channel,
                "chat_id": task.chat_id,
            },
        )
        self.scheduler.add_job(job)

    @staticmethod
    def _parse_datetime(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            dt = datetime.fromisoformat(value)
        except ValueError:
            return None
        return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)

    def _persist(self) -> None:
        now = datetime.now(UTC).isoformat()
        for task in self._tasks.values():
            task.updated_at = now
        self.store.save_all(self.list_tasks())


__all__ = [
    "ScheduleParseResult",
    "ScheduleService",
    "ScheduleStore",
    "ScheduleTask",
]
