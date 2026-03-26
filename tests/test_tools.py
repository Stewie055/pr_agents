from pathlib import Path

from pr_agents.infrastructure import ArtifactStore
from pr_agents.models import FileAnalysisInput, SourcePattern, TaskContext
from pr_agents.services import StubAnalysisPlatform
from pr_agents.tools.registry import WorkflowToolRegistry
from pr_agents.workflows import (
    DatabaseAnalysisWorkflow,
    FileAnalysisWorkflow,
    ReportFromExistingArtifactsWorkflow,
)


def test_tool_registry_runs_file_workflow_and_describes_dataset(tmp_path: Path) -> None:
    platform = StubAnalysisPlatform(ArtifactStore(str(tmp_path)))
    registry = WorkflowToolRegistry(
        file_workflow=FileAnalysisWorkflow(platform),
        database_workflow=DatabaseAnalysisWorkflow(platform),
        report_workflow=ReportFromExistingArtifactsWorkflow(platform),
    )
    result = registry.run_file_analysis(
        TaskContext(user_request="tool run", workspace=str(tmp_path)),
        FileAnalysisInput(
            business_code="A001",
            file_name="demo.csv",
            content="a,b\n1,2\n",
            objective="analyze",
            source_profile={"source_pattern": SourcePattern.PER_BUSINESS_FILE.value},
        ),
    )

    assert result.ok is True
    assert result.dataset is not None
    description = registry.describe_dataset(result.context, result.dataset)
    assert description["row_count"] == 1
    assert description["columns"] == ["a", "b"]
    assert description["metadata"]["business_code"] == "A001"
