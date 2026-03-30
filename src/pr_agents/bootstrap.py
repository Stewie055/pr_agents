from __future__ import annotations

from fastapi import FastAPI

from pr_agents.api import create_api_app
from pr_agents.agent.factory import build_agent_runtime
from pr_agents.application import AnalysisExecutionService, AgentSessionService, TaskApplicationService
from pr_agents.infrastructure import ArtifactStore
from pr_agents.infrastructure.sqlite import AgentSessionRepository, ArtifactRepository, TaskRepository
from pr_agents.services import StubAnalysisPlatform
from pr_agents.settings import Settings
from pr_agents.tools import WorkflowToolRegistry
from pr_agents.workflows import (
    DatabaseAnalysisWorkflow,
    FileAnalysisWorkflow,
    ReportFromExistingArtifactsWorkflow,
)


def build_components(
    settings: Settings | None = None,
) -> tuple[TaskApplicationService, AgentSessionService]:
    settings = settings or Settings()
    artifact_store = ArtifactStore(base_dir=settings.artifact_base_dir)
    platform = StubAnalysisPlatform(artifact_store=artifact_store)
    tools = WorkflowToolRegistry(
        file_workflow=FileAnalysisWorkflow(platform),
        database_workflow=DatabaseAnalysisWorkflow(platform),
        report_workflow=ReportFromExistingArtifactsWorkflow(platform),
    )
    execution_service = AnalysisExecutionService(tools)
    task_service = TaskApplicationService(
        execution_service=execution_service,
        task_repository=TaskRepository(settings.sqlite_path),
        artifact_repository=ArtifactRepository(settings.sqlite_path),
    )
    session_repository = AgentSessionRepository(settings.sqlite_path)
    runtime = build_agent_runtime(
        session_repository=session_repository,
        task_service=task_service,
        settings=settings,
        demo_data_path="examples/demo_a.csv",
    )
    agent_session_service = AgentSessionService(
        session_repository=session_repository,
        task_service=task_service,
        runtime=runtime,
        demo_data_path="examples/demo_a.csv",
    )
    return task_service, agent_session_service


def build_api_app(settings: Settings | None = None) -> FastAPI:
    task_service, agent_session_service = build_components(settings)
    return create_api_app(task_service, agent_session_service)
