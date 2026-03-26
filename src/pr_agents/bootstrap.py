from __future__ import annotations

from fastapi import FastAPI

from pr_agents.api import create_api_app
from pr_agents.agent import AgentDependencies, AnalysisOrchestrator
from pr_agents.application import TaskApplicationService
from pr_agents.infrastructure import ArtifactStore
from pr_agents.infrastructure.sqlite import ArtifactRepository, TaskRepository
from pr_agents.services import StubAnalysisPlatform
from pr_agents.settings import Settings
from pr_agents.tools import WorkflowToolRegistry
from pr_agents.webui import WebUIFacade
from pr_agents.workflows import (
    DatabaseAnalysisWorkflow,
    FileAnalysisWorkflow,
    ReportFromExistingArtifactsWorkflow,
)


def build_components(settings: Settings | None = None) -> tuple[WebUIFacade, TaskApplicationService]:
    settings = settings or Settings()
    artifact_store = ArtifactStore(base_dir=settings.artifact_base_dir)
    platform = StubAnalysisPlatform(artifact_store=artifact_store)
    tools = WorkflowToolRegistry(
        file_workflow=FileAnalysisWorkflow(platform),
        database_workflow=DatabaseAnalysisWorkflow(platform),
        report_workflow=ReportFromExistingArtifactsWorkflow(platform),
    )
    orchestrator = AnalysisOrchestrator(AgentDependencies(tools=tools))
    task_service = TaskApplicationService(
        orchestrator=orchestrator,
        task_repository=TaskRepository(settings.sqlite_path),
        artifact_repository=ArtifactRepository(settings.sqlite_path),
    )
    return WebUIFacade(orchestrator), task_service


def build_app(base_dir: str = "artifacts") -> WebUIFacade:
    settings = Settings(artifact_base_dir=base_dir, sqlite_path=f"{base_dir}/app.db")
    webui, _ = build_components(settings)
    return webui


def build_api_app(settings: Settings | None = None) -> FastAPI:
    _, task_service = build_components(settings)
    return create_api_app(task_service)
