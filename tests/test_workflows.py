from pathlib import Path

from pr_agents.infrastructure import ArtifactStore
from pr_agents.models import AnalysisResult, DatasetRef, FileAnalysisInput, ReportGenerationInput, TaskContext
from pr_agents.services import StubAnalysisPlatform
from pr_agents.workflows import FileAnalysisWorkflow, ReportFromExistingArtifactsWorkflow


def test_file_analysis_workflow_runs_end_to_end(tmp_path: Path) -> None:
    platform = StubAnalysisPlatform(ArtifactStore(str(tmp_path)))
    workflow = FileAnalysisWorkflow(platform)
    result = workflow.run(
        TaskContext(user_request="run file workflow", workspace=str(tmp_path)),
        FileAnalysisInput(file_name="demo.csv", content="x,y\n1,2\n", objective="build report"),
    )

    assert result.ok is True
    assert result.dataset is not None
    assert result.analysis is not None
    assert result.chart is not None
    assert result.report is not None
    assert len(result.artifacts) == 3


def test_report_workflow_uses_existing_artifacts(tmp_path: Path) -> None:
    platform = StubAnalysisPlatform(ArtifactStore(str(tmp_path)))
    dataset = platform.parse_file(
        TaskContext(user_request="seed", workspace=str(tmp_path)),
        "demo.csv",
        "x,y\n1,2\n",
    )
    analysis = AnalysisResult(summary="done", dataset_id=dataset.dataset_id)
    workflow = ReportFromExistingArtifactsWorkflow(platform)

    result = workflow.run(
        TaskContext(user_request="report", workspace=str(tmp_path)),
        ReportGenerationInput(objective="report only", dataset=dataset, analysis=analysis),
    )

    assert result.ok is True
    assert result.report is not None
