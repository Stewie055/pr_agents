from __future__ import annotations

from pathlib import Path

from pr_agents.application.tasks import TaskApplicationService
from pr_agents.infrastructure import AgentSessionRepository
from pr_agents.models import IntentMode
from pr_agents.settings import Settings

from .context import ContextManager
from .llm import FakeLLM, GLMProvider
from .memory import MemoryManager
from .planner_agent import PlannerAgent
from .react_agent import ReactAgent
from .runtime import AgentRuntime


def build_agent_runtime(
    *,
    session_repository: AgentSessionRepository,
    task_service: TaskApplicationService,
    settings: Settings,
    demo_data_path: str,
) -> AgentRuntime:
    fake_llm = FakeLLM()
    if settings.intent_mode == IntentMode.LLM:
        llm = GLMProvider(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
        )
        mode = IntentMode.LLM.value
    else:
        llm = fake_llm
        mode = IntentMode.FAKE.value

    memory_manager = MemoryManager(session_repository, task_service)
    context_manager = ContextManager(session_repository, task_service, memory_manager)
    planner_agent = PlannerAgent(
        llm=llm,
        model_name=settings.llm_model,
        timeout=settings.llm_timeout,
        fallback_llm=fake_llm,
        mode=mode,
    )
    react_agent = ReactAgent(
        llm=llm,
        model_name=settings.llm_model,
        timeout=settings.llm_timeout,
        fallback_llm=fake_llm,
        mode=mode,
        allowed_tools={
            "run_file_analysis_workflow",
            "run_db_analysis_workflow",
            "load_latest_report",
            "summarize_report",
        },
    )
    return AgentRuntime(
        session_repository=session_repository,
        task_service=task_service,
        context_manager=context_manager,
        planner_agent=planner_agent,
        react_agent=react_agent,
        demo_data_path=Path(demo_data_path),
        mode=mode,
    )
