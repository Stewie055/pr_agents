from __future__ import annotations

from pathlib import Path

from pr_agents.application.tasks import TaskApplicationService
from pr_agents.infrastructure import AgentSessionRepository
from pr_agents.settings import Settings

from .context import ContextManager
from .llm import build_agent_model
from .memory import MemoryManager
from .runtime import AgentRuntime


def build_agent_runtime(
    *,
    session_repository: AgentSessionRepository,
    task_service: TaskApplicationService,
    settings: Settings,
    demo_data_path: str,
) -> AgentRuntime:
    model, mode = build_agent_model(settings)
    memory_manager = MemoryManager(session_repository, task_service)
    context_manager = ContextManager(session_repository, task_service, memory_manager)
    return AgentRuntime(
        session_repository=session_repository,
        task_service=task_service,
        context_manager=context_manager,
        agent_model=model,
        demo_data_path=Path(demo_data_path),
        mode=mode,
    )
