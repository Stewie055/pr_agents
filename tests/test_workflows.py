from pathlib import Path

from pr_agents.infrastructure import ArtifactStore
from pr_agents.models import AnalysisResult, FileAnalysisInput, ReportGenerationInput, SourcePattern, TaskContext
from pr_agents.services import StubAnalysisPlatform
from pr_agents.workflows import FileAnalysisWorkflow, ReportFromExistingArtifactsWorkflow


def test_file_analysis_workflow_runs_end_to_end(tmp_path: Path) -> None:
    platform = StubAnalysisPlatform(ArtifactStore(str(tmp_path)))
    workflow = FileAnalysisWorkflow(platform)
    result = workflow.run(
        TaskContext(user_request="run file workflow", workspace=str(tmp_path)),
        FileAnalysisInput(
            business_code="A001",
            file_name="demo.csv",
            content="x,y\n1,2\n",
            objective="build report",
        ),
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
        "A001",
        {"source_pattern": SourcePattern.PER_BUSINESS_FILE.value},
    )
    analysis = AnalysisResult(summary="done", dataset_id=dataset.dataset_id, metadata={"business_code": "A001"})
    workflow = ReportFromExistingArtifactsWorkflow(platform)

    result = workflow.run(
        TaskContext(user_request="report", workspace=str(tmp_path)),
        ReportGenerationInput(
            business_code="A001",
            objective="report only",
            dataset=dataset,
            analysis=analysis,
        ),
    )

    assert result.ok is True
    assert result.report is not None


def test_file_analysis_workflow_supports_shared_file_and_scientific_plot(tmp_path: Path) -> None:
    platform = StubAnalysisPlatform(ArtifactStore(str(tmp_path)))
    workflow = FileAnalysisWorkflow(platform)
    result = workflow.run(
        TaskContext(user_request="run shared workflow", workspace=str(tmp_path)),
        FileAnalysisInput(
            business_code="B001",
            file_name="shared.csv",
            content="business_code,value\nB001,1\nB002,2\nB001,3\n",
            objective="build report",
            source_profile={"source_pattern": SourcePattern.SHARED_FILE.value},
            chart_profile={"chart_type": "scientific_plot"},
        ),
    )

    assert result.ok is True
    assert result.dataset is not None
    assert result.dataset.row_count == 2
    assert result.chart is not None
    assert result.chart.chart_type == "scientific_plot"
