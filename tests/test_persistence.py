from pathlib import Path

from pr_agents.application import AnalysisExecutionService, TaskApplicationService
from pr_agents.infrastructure import ArtifactRepository, ArtifactStore, TaskRepository
from pr_agents.models import FileAnalysisRequest
from pr_agents.services import StubAnalysisPlatform
from pr_agents.tools import WorkflowToolRegistry
from pr_agents.workflows import DatabaseAnalysisWorkflow, FileAnalysisWorkflow, ReportFromExistingArtifactsWorkflow


def build_task_service(tmp_path: Path) -> TaskApplicationService:
    artifact_store = ArtifactStore(str(tmp_path / "artifacts"))
    platform = StubAnalysisPlatform(artifact_store)
    tools = WorkflowToolRegistry(
        file_workflow=FileAnalysisWorkflow(platform),
        database_workflow=DatabaseAnalysisWorkflow(platform),
        report_workflow=ReportFromExistingArtifactsWorkflow(platform),
    )
    db_path = str(tmp_path / "artifacts" / "app.db")
    return TaskApplicationService(
        execution_service=AnalysisExecutionService(tools),
        task_repository=TaskRepository(db_path),
        artifact_repository=ArtifactRepository(db_path),
    )


def test_task_service_persists_task_and_artifacts(tmp_path: Path) -> None:
    service = build_task_service(tmp_path)
    response = service.submit_file_analysis(
        FileAnalysisRequest(
            business_code="A001",
            objective="persist",
            file_name="demo.csv",
            content="a,b\n1,2\n",
        )
    )

    assert response.status.value == "succeeded"
    detail = service.get_task(response.task_id)
    assert detail is not None
    assert detail.task.status.value == "succeeded"
    assert detail.task.input_summary["business_code"] == "A001"
    assert len(detail.artifacts) == 3


def test_task_service_marks_failures(tmp_path: Path) -> None:
    class FailingExecutionService:
        def run_file_analysis(self, context, request):
            raise RuntimeError("boom")

    db_path = str(tmp_path / "artifacts" / "app.db")
    service = TaskApplicationService(
        execution_service=FailingExecutionService(),
        task_repository=TaskRepository(db_path),
        artifact_repository=ArtifactRepository(db_path),
    )

    response = service.submit_file_analysis(
        FileAnalysisRequest(
            business_code="A001",
            objective="fail",
            file_name="demo.csv",
            content="a,b\n1,2\n",
        )
    )

    assert response.status.value == "failed"
    detail = service.get_task(response.task_id)
    assert detail is not None
    assert detail.task.status.value == "failed"
    assert detail.task.error_summary["message"] == "boom"
