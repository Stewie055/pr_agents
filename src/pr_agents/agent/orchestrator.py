from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext

from pr_agents.models import (
    DatabaseAnalysisInput,
    FileAnalysisInput,
    TaskContext,
    WorkflowResult,
)
from pr_agents.tools.registry import WorkflowToolRegistry


class UserTask(BaseModel):
    route: Literal["file_analysis", "db_analysis"]
    business_code: str
    objective: str
    file_name: str | None = None
    content: str | None = None
    query_name: str | None = None
    sql: str | None = None
    operations: list[str] = ["clean", "analyze", "visualize", "report"]
    source_profile: dict = Field(default_factory=dict)
    clean_profile: dict = Field(default_factory=dict)
    analysis_profile: dict = Field(default_factory=dict)
    chart_profile: dict = Field(default_factory=dict)
    report_profile: dict = Field(default_factory=dict)


@dataclass
class AgentDependencies:
    tools: WorkflowToolRegistry
    sessions: dict[str, list[WorkflowResult]] = field(default_factory=dict)


class AnalysisOrchestrator:
    """Routes normalized user tasks through PydanticAI-registered tools."""

    def __init__(self, deps: AgentDependencies) -> None:
        self.deps = deps
        self.agent = Agent(
            "test",
            deps_type=AgentDependencies,
            output_type=WorkflowResult,
            system_prompt=(
                "Route normalized analysis requests to the correct workflow tool. "
                "Do not invent domain logic."
            ),
        )
        self._register_tools()

    def _register_tools(self) -> None:
        @self.agent.tool
        def run_file_analysis(ctx: RunContext[AgentDependencies], task: UserTask) -> WorkflowResult:
            context = TaskContext(user_request=task.objective)
            result = ctx.deps.tools.run_file_analysis(
                context,
                FileAnalysisInput(
                    business_code=task.business_code,
                    file_name=task.file_name or "input.csv",
                    content=task.content or "",
                    objective=task.objective,
                    operations=task.operations,
                    source_profile=task.source_profile,
                    clean_profile=task.clean_profile,
                    analysis_profile=task.analysis_profile,
                    chart_profile=task.chart_profile,
                    report_profile=task.report_profile,
                ),
            )
            ctx.deps.sessions.setdefault(context.session_id, []).append(result)
            return result

        @self.agent.tool
        def run_db_analysis(ctx: RunContext[AgentDependencies], task: UserTask) -> WorkflowResult:
            context = TaskContext(user_request=task.objective)
            result = ctx.deps.tools.run_db_analysis(
                context,
                DatabaseAnalysisInput(
                    business_code=task.business_code,
                    query_name=task.query_name or "default_query",
                    sql=task.sql or "select 1",
                    objective=task.objective,
                    operations=task.operations,
                    source_profile=task.source_profile,
                    clean_profile=task.clean_profile,
                    analysis_profile=task.analysis_profile,
                    chart_profile=task.chart_profile,
                    report_profile=task.report_profile,
                ),
            )
            ctx.deps.sessions.setdefault(context.session_id, []).append(result)
            return result

    def route_task(self, task: UserTask, context: TaskContext | None = None) -> WorkflowResult:
        context = context or TaskContext(user_request=task.objective)
        if task.route == "file_analysis":
            result = self.deps.tools.run_file_analysis(
                context,
                FileAnalysisInput(
                    business_code=task.business_code,
                    file_name=task.file_name or "input.csv",
                    content=task.content or "",
                    objective=task.objective,
                    operations=task.operations,
                    source_profile=task.source_profile,
                    clean_profile=task.clean_profile,
                    analysis_profile=task.analysis_profile,
                    chart_profile=task.chart_profile,
                    report_profile=task.report_profile,
                ),
            )
        else:
            result = self.deps.tools.run_db_analysis(
                context,
                DatabaseAnalysisInput(
                    business_code=task.business_code,
                    query_name=task.query_name or "default_query",
                    sql=task.sql or "select 1",
                    objective=task.objective,
                    operations=task.operations,
                    source_profile=task.source_profile,
                    clean_profile=task.clean_profile,
                    analysis_profile=task.analysis_profile,
                    chart_profile=task.chart_profile,
                    report_profile=task.report_profile,
                ),
            )
        self.deps.sessions.setdefault(context.session_id, []).append(result)
        return result
