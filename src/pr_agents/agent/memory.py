from __future__ import annotations

from typing import TYPE_CHECKING

from pr_agents.models import MemorySnapshot, MidTermMemory, ShortTermMemory

if TYPE_CHECKING:
    from pr_agents.application.tasks import TaskApplicationService
    from pr_agents.infrastructure import AgentSessionRepository


class MemoryManager:
    def __init__(self, session_repository: AgentSessionRepository, task_service: TaskApplicationService) -> None:
        self.session_repository = session_repository
        self.task_service = task_service

    def snapshot(self, session_id: str) -> MemorySnapshot:
        messages = self.session_repository.list_messages(session_id)
        tasks = self.task_service.list_session_tasks(session_id)
        short_term = ShortTermMemory(
            recent_messages=[
                {
                    "role": message.role.value,
                    "message_type": message.message_type.value,
                    "content": message.content,
                    "metadata": message.metadata,
                }
                for message in messages[-6:]
            ]
        )
        mid_term = MidTermMemory()
        if tasks:
            latest_task = tasks[-1]
            mid_term.latest_task_summary = {
                "task_id": latest_task.task_id,
                "status": latest_task.status.value,
                "objective": latest_task.objective,
                "business_code": latest_task.input_summary.get("business_code"),
                "task_type": latest_task.task_type,
            }
            detail = self.task_service.get_task(latest_task.task_id)
            if detail and detail.result and detail.result.report:
                mid_term.latest_report_summary = detail.result.report.summary
                mid_term.latest_report_artifact_id = detail.result.report.artifact.artifact_id
        return MemorySnapshot(short_term=short_term, mid_term=mid_term, knowledge=[])
