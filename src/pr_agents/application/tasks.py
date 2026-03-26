from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from pr_agents.agent import AnalysisOrchestrator
from pr_agents.agent.orchestrator import UserTask
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
    WorkflowError,
    WorkflowResult,
)


class TaskApplicationService:
    def __init__(
        self,
        orchestrator: AnalysisOrchestrator,
        task_repository: TaskRepository,
        artifact_repository: ArtifactRepository,
    ) -> None:
        self.orchestrator = orchestrator
        self.task_repository = task_repository
        self.artifact_repository = artifact_repository
        self._results: dict[str, WorkflowResult] = {}

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
            result = self.orchestrator.route_task(
                UserTask(
                    route="file_analysis",
                    business_code=request.business_code,
                    objective=request.objective,
                    file_name=request.file_name,
                    content=request.content,
                    operations=request.operations,
                    source_profile=request.source_profile,
                    clean_profile=request.clean_profile,
                    analysis_profile=request.analysis_profile,
                    chart_profile=request.chart_profile,
                    report_profile=request.report_profile,
                ),
                context=context,
            )
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
            result = self.orchestrator.route_task(
                UserTask(
                    route="db_analysis",
                    business_code=request.business_code,
                    objective=request.objective,
                    query_name=request.query_name,
                    sql=request.sql,
                    operations=request.operations,
                    source_profile=request.source_profile,
                    clean_profile=request.clean_profile,
                    analysis_profile=request.analysis_profile,
                    chart_profile=request.chart_profile,
                    report_profile=request.report_profile,
                ),
                context=context,
            )
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

    def get_task(self, task_id: str) -> TaskDetailResponse | None:
        task = self.task_repository.get_task(task_id)
        if task is None:
            return None
        return TaskDetailResponse(
            task=task,
            artifacts=self.artifact_repository.list_task_artifacts(task_id),
            result=self._results.get(task_id),
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

    def _create_context(self, session_id: str | None, objective: str) -> TaskContext:
        context = TaskContext(user_request=objective)
        if session_id:
            context.session_id = session_id
        context.task_id = f"task-{uuid4().hex[:8]}"
        return context

    def _finalize_task(self, task_id: str, session_id: str, result: WorkflowResult) -> TaskResponse:
        self._results[task_id] = result
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
