from pathlib import Path

from pr_agents.agent import AgentDependencies, AnalysisOrchestrator
from pr_agents.agent.orchestrator import UserTask
from pr_agents.infrastructure import ArtifactStore
from pr_agents.services import StubAnalysisPlatform
from pr_agents.tools import WorkflowToolRegistry
from pr_agents.workflows import (
    DatabaseAnalysisWorkflow,
    FileAnalysisWorkflow,
    ReportFromExistingArtifactsWorkflow,
)


def build_orchestrator(tmp_path: Path) -> AnalysisOrchestrator:
    platform = StubAnalysisPlatform(ArtifactStore(str(tmp_path)))
    tools = WorkflowToolRegistry(
        file_workflow=FileAnalysisWorkflow(platform),
        database_workflow=DatabaseAnalysisWorkflow(platform),
        report_workflow=ReportFromExistingArtifactsWorkflow(platform),
    )
    return AnalysisOrchestrator(AgentDependencies(tools=tools))


def test_orchestrator_routes_file_analysis(tmp_path: Path) -> None:
    orchestrator = build_orchestrator(tmp_path)
    result = orchestrator.route_task(
        UserTask(route="file_analysis", objective="analyze file", file_name="demo.csv", content="a,b\n1,2\n")
    )

    assert result.ok is True
    assert result.dataset is not None
    assert result.dataset.source_uri == "demo.csv"


def test_orchestrator_routes_db_analysis(tmp_path: Path) -> None:
    orchestrator = build_orchestrator(tmp_path)
    result = orchestrator.route_task(
        UserTask(route="db_analysis", objective="analyze db", query_name="sales", sql="select * from sales")
    )

    assert result.ok is True
    assert result.dataset is not None
    assert result.dataset.source_uri == "sales"
