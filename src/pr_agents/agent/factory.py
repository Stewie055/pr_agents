from __future__ import annotations

from pr_agents.application.tasks import TaskApplicationService
from pr_agents.infrastructure import AgentSessionRepository
from pr_agents.settings import Settings

from .context import ContextManager
from .llm import build_agent_models
from .memory import MemoryManager
from .runtime import AgentRuntime


def build_agent_runtime(
    *,
    session_repository: AgentSessionRepository,
    task_service: TaskApplicationService,
    settings: Settings,
    demo_data_path: str,
) -> AgentRuntime:
    model, fallback_model, mode = build_agent_models(settings)
    memory_manager = MemoryManager(session_repository, task_service)
    context_manager = ContextManager(session_repository, task_service, memory_manager)
    return AgentRuntime(
        session_repository=session_repository,
        task_service=task_service,
        context_manager=context_manager,
        agent_model=model,
        fallback_agent_model=fallback_model,
        mode=mode,
    )
