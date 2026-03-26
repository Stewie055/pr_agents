from __future__ import annotations

from typing import TYPE_CHECKING

from pr_agents.models import AgentContext

from .memory import MemoryManager

if TYPE_CHECKING:
    from pr_agents.application.tasks import TaskApplicationService
    from pr_agents.infrastructure import AgentSessionRepository


class ContextManager:
    def __init__(
        self,
        session_repository: AgentSessionRepository,
        task_service: TaskApplicationService,
        memory_manager: MemoryManager,
    ) -> None:
        self.session_repository = session_repository
        self.task_service = task_service
        self.memory_manager = memory_manager

    def build_context(self, session_id: str, user_message: str) -> AgentContext:
        messages = self.session_repository.list_messages(session_id)
        tasks = self.task_service.list_session_tasks(session_id)
        memory = self.memory_manager.snapshot(session_id)
        latest_report_text = ""
        latest_report_summary = memory.mid_term.latest_report_summary
        latest_report_artifact_id = memory.mid_term.latest_report_artifact_id
        recent_artifacts: list[dict] = []

        if tasks:
            latest_task = tasks[-1]
            detail = self.task_service.get_task(latest_task.task_id)
            if detail:
                recent_artifacts = [
                    {
                        "artifact_id": artifact.artifact_id,
                        "artifact_type": artifact.artifact_type.value,
                        "filename": artifact.filename,
                    }
                    for artifact in detail.artifacts
                ]
                if latest_report_artifact_id:
                    latest_report_text = (
                        self.task_service.read_artifact_content(latest_report_artifact_id) or ""
                    )

        return AgentContext(
            session_id=session_id,
            user_message=user_message,
            conversation_window=[
                {
                    "role": message.role.value,
                    "message_type": message.message_type.value,
                    "content": message.content,
                    "metadata": message.metadata,
                }
                for message in messages[-10:]
            ],
            recent_tasks=[
                {
                    "task_id": task.task_id,
                    "status": task.status.value,
                    "objective": task.objective,
                    "task_type": task.task_type,
                    "business_code": task.input_summary.get("business_code"),
                }
                for task in tasks[-3:]
            ],
            recent_artifacts=recent_artifacts,
            latest_report_text=latest_report_text,
            latest_report_summary=latest_report_summary,
            latest_report_artifact_id=latest_report_artifact_id,
            memory=memory,
        )
