from __future__ import annotations

from fastapi import FastAPI

from pr_agents.api import create_api_app
from pr_agents.agent.intents import FakeIntentParser, GLMProvider, LLMIntentParser
from pr_agents.agent import (
    AgentDependencies,
    AnalysisOrchestrator,
    ConversationRouter,
    FakePlanner,
    LLMPlanner,
)
from pr_agents.application import AgentSessionService, TaskApplicationService
from pr_agents.infrastructure import ArtifactStore
from pr_agents.infrastructure.sqlite import AgentSessionRepository, ArtifactRepository, TaskRepository
from pr_agents.services import StubAnalysisPlatform
from pr_agents.settings import Settings
from pr_agents.tools import WorkflowToolRegistry
from pr_agents.webui import WebUIFacade
from pr_agents.workflows import (
    DatabaseAnalysisWorkflow,
    FileAnalysisWorkflow,
    ReportFromExistingArtifactsWorkflow,
)


def build_components(
    settings: Settings | None = None,
) -> tuple[WebUIFacade, TaskApplicationService, AgentSessionService]:
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
    fake_intent_parser = FakeIntentParser()
    router = ConversationRouter()
    fake_planner = FakePlanner()
    if settings.intent_mode.value == "llm":
        if settings.llm_provider.value != "glm":
            raise ValueError(f"unsupported llm provider: {settings.llm_provider.value}")
        provider = GLMProvider(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
        )
        intent_parser = LLMIntentParser(
            provider=provider,
            model=settings.llm_model,
            timeout=settings.llm_timeout,
            fallback_parser=fake_intent_parser,
        )
        planner = LLMPlanner(
            provider=provider,
            model=settings.llm_model,
            timeout=settings.llm_timeout,
            fallback_planner=fake_planner,
        )
    else:
        intent_parser = fake_intent_parser
        planner = fake_planner
    agent_session_service = AgentSessionService(
        session_repository=AgentSessionRepository(settings.sqlite_path),
        task_service=task_service,
        demo_data_path="examples/demo_a.csv",
        intent_parser=intent_parser,
        router=router,
        planner=planner,
    )
    return WebUIFacade(orchestrator), task_service, agent_session_service


def build_app(base_dir: str = "artifacts") -> WebUIFacade:
    settings = Settings(artifact_base_dir=base_dir, sqlite_path=f"{base_dir}/app.db")
    webui, _, _ = build_components(settings)
    return webui


def build_api_app(settings: Settings | None = None) -> FastAPI:
    _, task_service, agent_session_service = build_components(settings)
    return create_api_app(task_service, agent_session_service)
