from __future__ import annotations

from pr_agents.agent import AnalysisOrchestrator
from pr_agents.agent.orchestrator import UserTask
from pr_agents.models import WorkflowResult


class WebUIFacade:
    """Thin entrypoint representing the WebUI layer."""

    def __init__(self, orchestrator: AnalysisOrchestrator) -> None:
        self.orchestrator = orchestrator

    def submit(self, task: UserTask) -> WorkflowResult:
        return self.orchestrator.route_task(task)
