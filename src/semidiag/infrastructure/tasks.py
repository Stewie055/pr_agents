from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Lock
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

TaskStatus = Literal["pending", "running", "succeeded", "failed", "cancelled"]
TaskHandler = Callable[[dict[str, Any]], dict[str, Any]]


class TaskRecord(BaseModel):
    id: str = Field(default_factory=lambda: f"task_{uuid4().hex[:12]}")
    name: str
    status: TaskStatus = "pending"
    payload: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class InProcessTaskQueue:
    """Small process-local task queue for local deployments and deterministic tests."""

    def __init__(self, max_workers: int = 2) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="semidiag-task")
        self._tasks: dict[str, TaskRecord] = {}
        self._futures: dict[str, Future] = {}
        self._lock = Lock()

    def submit(self, *, name: str, payload: dict[str, Any], handler: TaskHandler) -> TaskRecord:
        task = TaskRecord(name=name, payload=payload)
        with self._lock:
            self._tasks[task.id] = task
        future = self._executor.submit(self._run, task.id, handler)
        with self._lock:
            self._futures[task.id] = future
        return task

    def get(self, task_id: str) -> TaskRecord | None:
        with self._lock:
            task = self._tasks.get(task_id)
            return task.model_copy(deep=True) if task else None

    def list_tasks(self) -> list[TaskRecord]:
        with self._lock:
            return [task.model_copy(deep=True) for task in self._tasks.values()]

    def cancel(self, task_id: str) -> TaskRecord | None:
        with self._lock:
            task = self._tasks.get(task_id)
            future = self._futures.get(task_id)
            if task is None:
                return None
            if task.status == "pending" and future and future.cancel():
                task.status = "cancelled"
                task.updated_at = datetime.now(UTC)
            return task.model_copy(deep=True)

    def wait(self, task_id: str, timeout: float | None = None) -> TaskRecord | None:
        with self._lock:
            future = self._futures.get(task_id)
        if future is not None:
            future.result(timeout=timeout)
        return self.get(task_id)

    def _run(self, task_id: str, handler: TaskHandler) -> None:
        with self._lock:
            task = self._tasks[task_id]
            task.status = "running"
            task.updated_at = datetime.now(UTC)
            payload = dict(task.payload)
        try:
            result = handler(payload)
        except Exception as exc:
            with self._lock:
                task = self._tasks[task_id]
                task.status = "failed"
                task.error = str(exc)
                task.updated_at = datetime.now(UTC)
            return
        with self._lock:
            task = self._tasks[task_id]
            task.status = "succeeded"
            task.result = result
            task.updated_at = datetime.now(UTC)
