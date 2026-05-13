from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Lock
from typing import Any, Literal

from semidiag.domain import TaskRecord
from semidiag.infrastructure.repository import SQLiteRepository

TaskStatus = Literal["pending", "running", "succeeded", "failed", "cancelled", "interrupted"]
TaskHandler = Callable[[dict[str, Any]], dict[str, Any]]


class InProcessTaskQueue:
    """Process-local executor with optional SQLite task record persistence."""

    def __init__(self, max_workers: int = 2, repository: SQLiteRepository | None = None) -> None:
        self.repository = repository
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="semidiag-task")
        self._tasks: dict[str, TaskRecord] = {}
        self._futures: dict[str, Future] = {}
        self._lock = Lock()
        if self.repository is not None:
            self.repository.mark_unfinished_tasks_interrupted()
            self._tasks = {task.id: task for task in self.repository.list_tasks()}

    def submit(
        self,
        *,
        name: str,
        payload: dict[str, Any],
        handler: TaskHandler,
        case_id: str | None = None,
        created_by: str = "system",
    ) -> TaskRecord:
        task = TaskRecord(name=name, payload=payload, case_id=case_id, created_by=created_by)
        with self._lock:
            self._tasks[task.id] = task
            self._persist(task)
        future = self._executor.submit(self._run, task.id, handler)
        with self._lock:
            self._futures[task.id] = future
        return task.model_copy(deep=True)

    def get(self, task_id: str) -> TaskRecord | None:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None and self.repository is not None:
                task = self.repository.get_task(task_id)
                if task is not None:
                    self._tasks[task.id] = task
            return task.model_copy(deep=True) if task else None

    def list_tasks(self, *, case_id: str | None = None) -> list[TaskRecord]:
        with self._lock:
            if self.repository is not None:
                tasks = self.repository.list_case_tasks(case_id) if case_id else self.repository.list_tasks()
                self._tasks.update({task.id: task for task in tasks})
            else:
                tasks = list(self._tasks.values())
            if case_id:
                tasks = [task for task in tasks if task.case_id == case_id]
            return [task.model_copy(deep=True) for task in tasks]

    def cancel(self, task_id: str) -> TaskRecord | None:
        with self._lock:
            task = self._tasks.get(task_id) or (self.repository.get_task(task_id) if self.repository else None)
            future = self._futures.get(task_id)
            if task is None:
                return None
            if task.status == "pending" and future and future.cancel():
                task.status = "cancelled"
                task.updated_at = datetime.now(UTC)
                task.finished_at = task.updated_at
                self._tasks[task.id] = task
                self._persist(task)
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
            if task.status == "cancelled":
                return
            task.status = "running"
            task.started_at = datetime.now(UTC)
            task.updated_at = task.started_at
            payload = dict(task.payload)
            self._persist(task)
        try:
            result = handler(payload)
        except Exception as exc:
            with self._lock:
                task = self._tasks[task_id]
                task.status = "failed"
                task.error = str(exc)
                task.updated_at = datetime.now(UTC)
                task.finished_at = task.updated_at
                self._persist(task)
            return
        with self._lock:
            task = self._tasks[task_id]
            task.status = "succeeded"
            task.result = result
            task.artifact_ids = [str(item) for item in result.get("artifact_ids", [])]
            task.evidence_ids = [str(item) for item in result.get("evidence_ids", [])]
            task.updated_at = datetime.now(UTC)
            task.finished_at = task.updated_at
            self._persist(task)

    def _persist(self, task: TaskRecord) -> None:
        if self.repository is not None:
            self.repository.upsert_task(task)
