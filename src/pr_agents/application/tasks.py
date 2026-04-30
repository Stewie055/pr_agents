from __future__ import annotations

import mimetypes
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

from pr_agents.infrastructure import ArtifactRepository, TaskRepository
from pr_agents.models import (
    ArtifactRecord,
    ArtifactRef,
    DatabaseAnalysisRequest,
    FileAnalysisRequest,
    TaskContext,
    TaskDetailResponse,
    TaskRecord,
    TaskResponse,
    TaskStatus,
    AgentSourceRecord,
    AgentSourceType,
    CancelTaskResponse,
    WorkflowError,
    WorkflowResult,
)
from .execution import AnalysisExecutionService


class TaskApplicationService:
    def __init__(
        self,
        execution_service: AnalysisExecutionService,
        task_repository: TaskRepository,
        artifact_repository: ArtifactRepository,
    ) -> None:
        self.execution_service = execution_service
        self.task_repository = task_repository
        self.artifact_repository = artifact_repository
        self._results: dict[str, WorkflowResult] = {}
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="analysis-task")
        self._cancel_flags: dict[str, threading.Event] = {}

    def submit_file_analysis(self, request: FileAnalysisRequest) -> TaskResponse:
        context = self._create_context(request.session_id, request.objective)
        self.task_repository.create_task(
            task_id=context.task_id,
            session_id=context.session_id,
            task_type="file_analysis",
            objective=request.objective,
            input_summary={
                "business_code": request.business_code,
                "file_name": request.file_name,
                "operations": request.operations,
            },
        )
        self.task_repository.update_task_status(context.task_id, TaskStatus.RUNNING)
        try:
            result = self._execute_file_analysis(context, request)
            return self._finalize_task(context.task_id, context.session_id, result)
        except Exception as exc:
            error = WorkflowError(code="task_execution_failed", message=str(exc), step="application_service")
            self.task_repository.update_task_status(
                context.task_id,
                TaskStatus.FAILED,
                error_summary=error.model_dump(mode="json"),
            )
            return TaskResponse(
                task_id=context.task_id,
                session_id=context.session_id,
                status=TaskStatus.FAILED,
                error=error,
            )

    def submit_db_analysis(self, request: DatabaseAnalysisRequest) -> TaskResponse:
        context = self._create_context(request.session_id, request.objective)
        self.task_repository.create_task(
            task_id=context.task_id,
            session_id=context.session_id,
            task_type="db_analysis",
            objective=request.objective,
            input_summary={
                "business_code": request.business_code,
                "query_name": request.query_name,
                "operations": request.operations,
            },
        )
        self.task_repository.update_task_status(context.task_id, TaskStatus.RUNNING)
        try:
            result = self._execute_db_analysis(context, request)
            return self._finalize_task(context.task_id, context.session_id, result)
        except Exception as exc:
            error = WorkflowError(code="task_execution_failed", message=str(exc), step="application_service")
            self.task_repository.update_task_status(
                context.task_id,
                TaskStatus.FAILED,
                error_summary=error.model_dump(mode="json"),
            )
            return TaskResponse(
                task_id=context.task_id,
                session_id=context.session_id,
                status=TaskStatus.FAILED,
                error=error,
            )

    def submit_source_analysis_async(
        self,
        *,
        session_id: str,
        source: AgentSourceRecord,
        objective: str,
    ) -> TaskResponse:
        request = self._request_from_source(session_id, source, objective)
        task_type = "file_analysis" if source.source_type == AgentSourceType.CSV_FILE else "db_analysis"
        context = self._create_context(session_id, objective)
        self.task_repository.create_task(
            task_id=context.task_id,
            session_id=context.session_id,
            task_type=task_type,
            objective=objective,
            input_summary={
                "business_code": request.business_code,
                "source_id": source.source_id,
                "source_type": source.source_type.value,
                "source_name": source.name,
                "execution": "async",
            },
        )
        self.task_repository.update_task_status(context.task_id, TaskStatus.QUEUED)
        cancel_flag = threading.Event()
        self._cancel_flags[context.task_id] = cancel_flag
        self._executor.submit(self._run_background_task, context, request, task_type, cancel_flag)
        return TaskResponse(task_id=context.task_id, session_id=context.session_id, status=TaskStatus.QUEUED)

    def cancel_task(self, task_id: str) -> CancelTaskResponse:
        task = self.task_repository.get_task(task_id)
        if task is None:
            return CancelTaskResponse(
                task_id=task_id,
                status=TaskStatus.FAILED,
                cancelled=False,
                message="task not found",
            )
        if task.status in {TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.CANCELLED}:
            return CancelTaskResponse(
                task_id=task_id,
                status=task.status,
                cancelled=False,
                message=f"task already {task.status.value}",
            )
        self._cancel_flags.setdefault(task_id, threading.Event()).set()
        if task.status == TaskStatus.QUEUED:
            updated = self.task_repository.update_task_status(
                task_id,
                TaskStatus.CANCELLED,
                error_summary={"code": "task_cancelled", "message": "Task cancelled before execution."},
            )
            return CancelTaskResponse(
                task_id=task_id,
                status=updated.status,
                cancelled=True,
                message="task cancelled",
            )
        return CancelTaskResponse(
            task_id=task_id,
            status=task.status,
            cancelled=True,
            message="cancellation requested",
        )

    def get_task(self, task_id: str) -> TaskDetailResponse | None:
        task = self.task_repository.get_task(task_id)
        if task is None:
            return None
        return TaskDetailResponse(
            task=task,
            artifacts=self.artifact_repository.list_task_artifacts(task_id),
            result=self._results.get(task_id) or self.task_repository.load_workflow_result(task_id),
        )

    def list_session_tasks(self, session_id: str) -> list[TaskRecord]:
        return self.task_repository.list_session_tasks(session_id)

    def get_artifact(self, artifact_id: str) -> ArtifactRecord | None:
        return self.artifact_repository.get_artifact(artifact_id)

    def read_artifact_content(self, artifact_id: str) -> str | None:
        artifact = self.get_artifact(artifact_id)
        if artifact is None:
            return None
        path = Path(artifact.uri)
        if not path.exists():
            return None
        suffix = path.suffix.lower()
        if suffix not in {".txt", ".md", ".json", ".csv"}:
            raise ValueError("artifact content type is not supported for inline reading")
        return path.read_text(encoding="utf-8")

    def read_artifact_raw(self, artifact_id: str) -> tuple[bytes, str] | None:
        artifact = self.get_artifact(artifact_id)
        if artifact is None:
            return None
        path = Path(artifact.uri)
        if not path.exists():
            return None
        media_type, _ = mimetypes.guess_type(path.name)
        return path.read_bytes(), media_type or "application/octet-stream"

    def wait_for_task(
        self,
        task_id: str,
        *,
        timeout_seconds: float = 30.0,
        poll_interval: float = 0.05,
    ) -> TaskDetailResponse | None:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            detail = self.get_task(task_id)
            if detail is None:
                return None
            if detail.task.status in {TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.CANCELLED}:
                return detail
            time.sleep(poll_interval)
        return self.get_task(task_id)

    def _create_context(self, session_id: str | None, objective: str) -> TaskContext:
        context = TaskContext(user_request=objective)
        if session_id:
            context.session_id = session_id
        context.task_id = f"task-{uuid4().hex[:8]}"
        return context

    def _run_background_task(
        self,
        context: TaskContext,
        request: FileAnalysisRequest | DatabaseAnalysisRequest,
        task_type: str,
        cancel_flag: threading.Event,
    ) -> None:
        if cancel_flag.is_set():
            self.task_repository.update_task_status(
                context.task_id,
                TaskStatus.CANCELLED,
                error_summary={"code": "task_cancelled", "message": "Task cancelled before execution."},
            )
            return
        self.task_repository.update_task_status(context.task_id, TaskStatus.RUNNING)
        try:
            if cancel_flag.is_set():
                raise _TaskCancelled("Task cancelled before business execution.")
            if task_type == "file_analysis":
                result = self._execute_file_analysis(context, request)  # type: ignore[arg-type]
            else:
                result = self._execute_db_analysis(context, request)  # type: ignore[arg-type]
            if cancel_flag.is_set():
                raise _TaskCancelled("Task cancelled after business execution.")
            self._finalize_task(context.task_id, context.session_id, result)
        except _TaskCancelled as exc:
            self.task_repository.update_task_status(
                context.task_id,
                TaskStatus.CANCELLED,
                error_summary={"code": "task_cancelled", "message": str(exc)},
            )
        except Exception as exc:  # pragma: no cover - exercised via API error state
            error = WorkflowError(code="task_execution_failed", message=str(exc), step="background_task")
            self.task_repository.update_task_status(
                context.task_id,
                TaskStatus.FAILED,
                error_summary=error.model_dump(mode="json"),
            )

    def _execute_file_analysis(self, context: TaskContext, request: FileAnalysisRequest) -> WorkflowResult:
        return self.execution_service.run_file_analysis(context, request)

    def _execute_db_analysis(self, context: TaskContext, request: DatabaseAnalysisRequest) -> WorkflowResult:
        return self.execution_service.run_db_analysis(context, request)

    def _request_from_source(
        self,
        session_id: str,
        source: AgentSourceRecord,
        objective: str,
    ) -> FileAnalysisRequest | DatabaseAnalysisRequest:
        source_profile = {
            **source.metadata.get("source_profile", {}),
            "source_id": source.source_id,
            "schema_summary": source.metadata.get("schema_summary", {}),
        }
        business_code = source.metadata.get("business_code")
        if source.source_type == AgentSourceType.CSV_FILE:
            content = source.payload.get("content")
            storage_ref = source.payload.get("storage_ref")
            if not content and storage_ref:
                content = Path(str(storage_ref)).read_text(encoding="utf-8")
            return FileAnalysisRequest(
                session_id=session_id,
                business_code=str(business_code or "file_analysis"),
                objective=objective,
                file_name=str(source.payload.get("file_name") or source.name),
                content=str(content or ""),
                source_profile=source_profile,
                chart_profile={"chart_type": "diagnostic_bar"},
                report_profile={"template": "structured-lab-report"},
            )
        return DatabaseAnalysisRequest(
            session_id=session_id,
            business_code=str(business_code or "db_analysis"),
            objective=objective,
            query_name=str(source.payload.get("query_name") or source.name),
            sql=str(source.payload.get("sql") or ""),
            source_profile=source_profile,
            chart_profile={"chart_type": "diagnostic_bar"},
            report_profile={"template": "structured-lab-report"},
        )

    def _finalize_task(self, task_id: str, session_id: str, result: WorkflowResult) -> TaskResponse:
        self._results[task_id] = result
        self.task_repository.save_workflow_result(task_id, result)
        for artifact in result.artifacts:
            self._register_artifact(task_id, artifact)
        status = TaskStatus.SUCCEEDED if result.ok else TaskStatus.FAILED
        error = result.errors[0] if result.errors else None
        self.task_repository.update_task_status(
            task_id,
            status,
            result_summary=self._build_result_summary(result),
            error_summary=error.model_dump(mode="json") if error else {},
        )
        return TaskResponse(
            task_id=task_id,
            session_id=session_id,
            status=status,
            result=result,
            error=error,
        )

    def _register_artifact(self, task_id: str, artifact: ArtifactRef) -> None:
        filename = Path(artifact.uri).name
        metadata = dict(artifact.metadata)
        metadata["artifact_id"] = artifact.artifact_id
        self.artifact_repository.register_artifact(
            task_id=task_id,
            artifact_type=artifact.artifact_type,
            uri=artifact.uri,
            filename=filename,
            metadata=metadata,
        )

    @staticmethod
    def _build_result_summary(result: WorkflowResult) -> dict:
        return {
            "ok": result.ok,
            "business_code": result.dataset.metadata.get("business_code") if result.dataset else None,
            "dataset_id": result.dataset.dataset_id if result.dataset else None,
            "chart_id": result.chart.chart_id if result.chart else None,
            "report_id": result.report.report_id if result.report else None,
            "error_count": len(result.errors),
        }


class _TaskCancelled(Exception):
    pass
