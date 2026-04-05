from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

logger = logging.getLogger("seju_lite.scheduler")

JobHandler = Callable[[], Awaitable[None] | None]


@dataclass(slots=True)
class ScheduledJob:
    """A lightweight interval-based scheduled job."""

    name: str
    interval_seconds: int
    handler: JobHandler
    run_immediately: bool = False
    enabled: bool = True
    last_run_at: datetime | None = None
    running: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def should_run(self, now: datetime) -> bool:
        if not self.enabled or self.running:
            return False
        if self.last_run_at is None:
            return self.run_immediately
        due_at = self.last_run_at + timedelta(seconds=self.interval_seconds)
        return now >= due_at


class Scheduler:
    """A simple async scheduler for recurring background jobs."""

    def __init__(self, *, tick_seconds: float = 1.0) -> None:
        self._tick_seconds = tick_seconds # 检查一次任务是否到时间
        self._jobs: dict[str, ScheduledJob] = {}
        self._loop_task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()

    @property
    def jobs(self) -> tuple[ScheduledJob, ...]:
        return tuple(self._jobs.values())

    def add_job(self, job: ScheduledJob) -> None:
        if job.interval_seconds <= 0:
            raise ValueError("interval_seconds must be > 0")
        if job.name in self._jobs:
            raise ValueError(f"Job already exists: {job.name}")
        self._jobs[job.name] = job

    def remove_job(self, name: str) -> ScheduledJob | None:
        return self._jobs.pop(name, None)

    async def start(self) -> None:
        if self._loop_task is not None and not self._loop_task.done():
            return
        self._stop_event = asyncio.Event() # 重置
        self._loop_task = asyncio.create_task(self._run_loop(), name="scheduler-loop")
        logger.info("Scheduler started with %s job(s)", len(self._jobs))

    async def stop(self) -> None:
        self._stop_event.set()
        if self._loop_task is None:
            return
        self._loop_task.cancel()
        try:
            await self._loop_task
        except asyncio.CancelledError:
            pass
        finally:
            self._loop_task = None
        logger.info("Scheduler stopped")

    async def run_pending(self) -> None:
        now = datetime.now(UTC)
        for job in self._jobs.values():
            if job.should_run(now):
                asyncio.create_task(self._run_job(job, now), name=f"scheduler-job:{job.name}")

    async def _run_loop(self) -> None:
        try:
            while not self._stop_event.is_set():
                await self.run_pending()
                await asyncio.sleep(self._tick_seconds)
        except asyncio.CancelledError:
            raise

    async def _run_job(self, job: ScheduledJob, now: datetime) -> None:
        job.running = True
        job.last_run_at = now
        logger.info("Running scheduled job: %s", job.name)
        try:
            result = job.handler() # 调用handler
            if inspect.isawaitable(result):
                await result
        except Exception:
            logger.exception("Scheduled job failed: %s", job.name)
        finally:
            job.running = False


__all__ = [
    "JobHandler",
    "ScheduledJob",
    "Scheduler",
]
