from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from pr_agents.models import (
    AgentContext,
    AgentDecision,
    AgentDecisionAction,
    AgentEntry,
    AgentMessageStartResponse,
    AgentPlan,
    AgentRunStatus,
    AgentStepStatus,
    AgentStreamEvent,
    DatabaseAnalysisRequest,
    FileAnalysisRequest,
    MessageRole,
    MessageType,
)

from .context import ContextManager
from .planner_agent import PlannerAgent
from .react_agent import ReactAgent

if TYPE_CHECKING:
    from pr_agents.application.tasks import TaskApplicationService
    from pr_agents.infrastructure import AgentSessionRepository


def event_timestamp() -> str:
    return datetime.now(UTC).isoformat()


class AgentRuntime:
    def __init__(
        self,
        *,
        session_repository: AgentSessionRepository,
        task_service: TaskApplicationService,
        context_manager: ContextManager,
        planner_agent: PlannerAgent,
        react_agent: ReactAgent,
        demo_data_path: Path,
        mode: str,
    ) -> None:
        self.session_repository = session_repository
        self.task_service = task_service
        self.context_manager = context_manager
        self.planner_agent = planner_agent
        self.react_agent = react_agent
        self.demo_data_path = demo_data_path
        self._mode = mode

    @property
    def mode(self) -> str:
        return getattr(self.react_agent, "mode", self._mode)

    def stream_run_events(self, session_id: str, run_id: str):
        run = self.session_repository.get_run(run_id)
        if run is None or run.session_id != session_id:
            yield self._event("run_failed", session_id, run_id, {"message": "run not found"})
            return
        if run.status != AgentRunStatus.PLANNED:
            yield self._snapshot_event(session_id, run_id)
            return

        request_content = run.metadata.get("request_content", run.goal)
        self.session_repository.update_run(
            run_id,
            AgentRunStatus.RUNNING,
            summary="Run started.",
            metadata={"state": "running"},
        )
        yield self._event(
            "run_started",
            session_id,
            run_id,
            {"goal": request_content, "intent_mode": self.mode},
        )

        context = self.context_manager.build_context(session_id, request_content)
        decision = self.react_agent.decide(context)

        if decision.action == AgentDecisionAction.RESPOND:
            yield from self._respond_directly(session_id, run_id, context, decision)
            return

        if decision.action == AgentDecisionAction.CALL_TOOL and decision.tool_name in {
            "load_latest_report",
            "summarize_report",
        }:
            yield from self._handle_report_tool(session_id, run_id, context, decision)
            return

        yield self._event(
            "planning_started",
            session_id,
            run_id,
            {
                "decision_source": decision.decision_source,
                "tool_name": decision.tool_name,
                "thought_summary": decision.thought_summary,
            },
        )
        plan = self.planner_agent.build_plan(
            context,
            decision.model_dump(mode="json"),
        )
        self.session_repository.update_run(
            run_id,
            AgentRunStatus.RUNNING,
            summary=f"Created plan with {len(plan.steps)} steps.",
            metadata={
                "business_code": plan.business_code,
                "entry": plan.entry.value,
                "decision_source": decision.decision_source,
                "decision_fallback": decision.used_fallback,
                "planner_source": plan.planner_source,
                "goal": plan.goal,
                "task_type": "analysis",
            },
        )
        steps = [
            self.session_repository.create_run_step(
                run_id=run_id,
                step_index=step.step_index,
                title=step.title,
                tool_name=step.tool_name,
                inputs_summary=step.inputs_summary,
            )
            for step in plan.steps
        ]
        self.session_repository.add_message(
            session_id,
            MessageRole.ASSISTANT,
            MessageType.PLAN,
            self._plan_summary(plan),
            metadata={
                "run_id": run_id,
                "business_code": plan.business_code,
                "entry": plan.entry.value,
                "planner_source": plan.planner_source,
                "intent_mode": self.mode,
            },
        )
        yield self._event(
            "plan_created",
            session_id,
            run_id,
            {
                "goal": plan.goal,
                "planner_source": plan.planner_source,
                "steps": [step.model_dump(mode="json") for step in steps],
            },
        )

        final_payload, failed, events = self._execute_plan(session_id, run_id, context, plan, steps)
        for event in events:
            yield event
        yield self._event("run_failed" if failed else "run_completed", session_id, run_id, final_payload)
        yield self._snapshot_event(session_id, run_id)

    def _respond_directly(self, session_id: str, run_id: str, context: AgentContext, decision: AgentDecision):
        message = self.session_repository.add_message(
            session_id,
            MessageRole.ASSISTANT,
            MessageType.CHAT,
            decision.response,
            metadata={
                "chat_only": True,
                "intent_mode": self.mode,
                "decision_source": decision.decision_source,
                "thought_summary": decision.thought_summary,
            },
        )
        self.session_repository.update_run(
            run_id,
            AgentRunStatus.SUCCEEDED,
            summary="Returned direct agent reply.",
            metadata={
                "chat_only": True,
                "message_id": message.message_id,
                "decision_source": decision.decision_source,
            },
        )
        yield self._event(
            "chat_reply",
            session_id,
            run_id,
            {"message": decision.response, "message_id": message.message_id},
        )
        yield self._event("run_completed", session_id, run_id, {"summary": "Returned direct agent reply."})
        yield self._snapshot_event(session_id, run_id)

    def _handle_report_tool(self, session_id: str, run_id: str, context: AgentContext, decision: AgentDecision):
        if not context.latest_report_artifact_id:
            error_message = "There is no completed report in this session yet. Run a demo workflow first."
            self.session_repository.add_message(
                session_id,
                MessageRole.ASSISTANT,
                MessageType.ERROR,
                error_message,
            )
            self.session_repository.update_run(run_id, AgentRunStatus.FAILED, summary=error_message)
            yield self._event("run_failed", session_id, run_id, {"message": error_message})
            yield self._snapshot_event(session_id, run_id)
            return

        if decision.tool_name == "summarize_report":
            business_code = (
                context.memory.mid_term.latest_task_summary.get("business_code") or "A_DEMO"
            )
            response_text = (
                f"Summary for {business_code}: {context.latest_report_summary} "
                "The full report is available if you want the complete text."
            )
            summary = "Returned latest report summary."
            summary_only = True
        else:
            response_text = context.latest_report_text
            summary = "Returned latest report."
            summary_only = False

        message = self.session_repository.add_message(
            session_id,
            MessageRole.ASSISTANT,
            MessageType.CHAT,
            response_text,
            metadata={
                "report_artifact_id": context.latest_report_artifact_id,
                "report_preview": context.latest_report_text,
                "summary_only": summary_only,
            },
        )
        self.session_repository.update_run(
            run_id,
            AgentRunStatus.SUCCEEDED,
            summary=summary,
            metadata={
                "report_artifact_id": context.latest_report_artifact_id,
                "summary_only": summary_only,
                "decision_source": decision.decision_source,
            },
        )
        yield self._event(
            "chat_reply",
            session_id,
            run_id,
            {
                "message": response_text,
                "message_id": message.message_id,
                "report_artifact_id": context.latest_report_artifact_id,
            },
        )
        yield self._event("run_completed", session_id, run_id, {"summary": summary})
        yield self._snapshot_event(session_id, run_id)

    def _execute_plan(self, session_id: str, run_id: str, context: AgentContext, plan: AgentPlan, steps):
        task_response = None
        result = None
        report_text = ""
        report_artifact_id = None
        events: list[AgentStreamEvent] = []
        for step in steps:
            self.session_repository.update_run_step(step.step_id, AgentStepStatus.RUNNING)
            events.append(
                self._event(
                    "step_started",
                    session_id,
                    run_id,
                    {
                        "step_id": step.step_id,
                        "step_index": step.step_index,
                        "title": step.title,
                        "tool_name": step.tool_name,
                    },
                )
            )
            if step.tool_name in {"run_file_analysis_workflow", "run_db_analysis_workflow"}:
                tool_name = "run_db_analysis" if plan.entry == AgentEntry.DATABASE else "run_file_analysis"
                self.session_repository.add_message(
                    session_id,
                    MessageRole.TOOL,
                    MessageType.TOOL_CALL,
                    tool_name,
                    metadata={
                        "run_id": run_id,
                        "step_id": step.step_id,
                        "business_code": plan.business_code,
                        "intent_mode": self.mode,
                    },
                )
                events.append(
                    self._event(
                        "tool_called",
                        session_id,
                        run_id,
                        {"step_id": step.step_id, "tool_name": tool_name, "business_code": plan.business_code},
                    )
                )
                task_response = self._run_analysis_task(session_id, context, plan)
                if task_response.error:
                    self.session_repository.update_run_step(
                        step.step_id,
                        AgentStepStatus.FAILED,
                        error_summary=task_response.error.model_dump(mode="json"),
                        task_id=task_response.task_id,
                    )
                    self.session_repository.update_run(
                        run_id,
                        AgentRunStatus.FAILED,
                        summary=f"Failed on step: {step.title}",
                    )
                    events.append(
                        self._event(
                            "tool_result",
                            session_id,
                            run_id,
                            {
                                "step_id": step.step_id,
                                "task_id": task_response.task_id,
                                "status": task_response.status.value,
                                "error": task_response.error.model_dump(mode="json"),
                            },
                        )
                    )
                    events.append(
                        self._event(
                            "step_failed",
                            session_id,
                            run_id,
                            {"step_id": step.step_id, "title": step.title, "message": task_response.error.message},
                        )
                    )
                    self.session_repository.add_message(
                        session_id,
                        MessageRole.ASSISTANT,
                        MessageType.ERROR,
                        f"Execution stopped at '{step.title}': {task_response.error.message}",
                        metadata={"run_id": run_id, "task_id": task_response.task_id},
                    )
                    return (
                        {"message": f"Execution stopped at '{step.title}': {task_response.error.message}"},
                        True,
                        events,
                    )
                result = task_response.result
                artifact_ids = [artifact.artifact_id for artifact in result.artifacts] if result else []
                report_artifact_id = result.report.artifact.artifact_id if result and result.report else None
                if report_artifact_id:
                    report_text = self.task_service.read_artifact_content(report_artifact_id) or ""
                self.session_repository.update_run_step(
                    step.step_id,
                    AgentStepStatus.SUCCEEDED,
                    observation_summary={
                        "task_status": task_response.status.value,
                        "chart_type": result.chart.chart_type if result and result.chart else None,
                        "report_summary": result.report.summary if result and result.report else None,
                    },
                    task_id=task_response.task_id,
                    artifact_ids=artifact_ids,
                )
                self.session_repository.add_message(
                    session_id,
                    MessageRole.TOOL,
                    MessageType.TOOL_RESULT,
                    f"Task {task_response.task_id} finished with status {task_response.status.value}.",
                    metadata={
                        "run_id": run_id,
                        "step_id": step.step_id,
                        "task_id": task_response.task_id,
                        "chart_type": result.chart.chart_type if result and result.chart else None,
                        "report_artifact_id": report_artifact_id,
                    },
                )
                events.append(
                    self._event(
                        "tool_result",
                        session_id,
                        run_id,
                        {
                            "step_id": step.step_id,
                            "task_id": task_response.task_id,
                            "status": task_response.status.value,
                            "chart_type": result.chart.chart_type if result and result.chart else None,
                            "report_artifact_id": report_artifact_id,
                        },
                    )
                )
                events.append(
                    self._event(
                        "step_completed",
                        session_id,
                        run_id,
                        {"step_id": step.step_id, "title": step.title, "task_id": task_response.task_id},
                    )
                )
            else:
                source_label = "database analysis" if plan.entry == AgentEntry.DATABASE else "file analysis"
                summary = (
                    f"Completed {source_label} for {plan.business_code}. "
                    f"Chart type: {result.chart.chart_type if result and result.chart else 'n/a'}. "
                    f"Report summary: {result.report.summary if result and result.report else 'n/a'}."
                )
                self.session_repository.update_run_step(
                    step.step_id,
                    AgentStepStatus.SUCCEEDED,
                    observation_summary={"summary": summary},
                    task_id=task_response.task_id if task_response else None,
                    artifact_ids=[report_artifact_id] if report_artifact_id else [],
                )
                events.append(
                    self._event(
                        "step_completed",
                        session_id,
                        run_id,
                        {"step_id": step.step_id, "title": step.title, "summary": summary},
                    )
                )

        source_label = "database analysis" if plan.entry == AgentEntry.DATABASE else "file analysis"
        final_content = (
            f"Completed {source_label} for {plan.business_code}. "
            f"Chart type: {result.chart.chart_type if result and result.chart else 'n/a'}. "
            f"Report summary: {result.report.summary if result and result.report else 'n/a'}."
        )
        self.session_repository.add_message(
            session_id,
            MessageRole.ASSISTANT,
            MessageType.CHAT,
            final_content,
            metadata={
                "run_id": run_id,
                "task_id": task_response.task_id if task_response else None,
                "report_artifact_id": report_artifact_id,
                "report_preview": report_text,
                "business_code": plan.business_code,
                "intent_mode": self.mode,
            },
        )
        self.session_repository.update_run(
            run_id,
            AgentRunStatus.SUCCEEDED,
            summary=f"Completed {len(steps)} planned steps.",
        )
        return (
            {
                "message": final_content,
                "task_id": task_response.task_id if task_response else None,
                "report_artifact_id": report_artifact_id,
                "summary": f"Completed {len(steps)} planned steps.",
            },
            False,
            events,
        )

    def _run_analysis_task(self, session_id: str, context: AgentContext, plan: AgentPlan):
        if plan.entry == AgentEntry.DATABASE:
            return self.task_service.submit_db_analysis(
                DatabaseAnalysisRequest(
                    business_code=plan.business_code,
                    objective=plan.goal,
                    query_name="demo_query",
                    sql="select * from cleaned_demo_data",
                    source_profile={"source_pattern": "per_business_file", "data_version": "demo-v1"},
                    chart_profile={"chart_type": "scientific_plot"},
                    report_profile={"template": "demo-template"},
                    session_id=session_id,
                )
            )
        return self.task_service.submit_file_analysis(
            FileAnalysisRequest(
                business_code=plan.business_code,
                objective=plan.goal,
                file_name=self.demo_data_path.name,
                content=self.demo_data_path.read_text(encoding="utf-8"),
                source_profile={"source_pattern": "per_business_file", "data_version": "demo-v1"},
                chart_profile={"chart_type": "scientific_plot"},
                report_profile={"template": "demo-template"},
                session_id=session_id,
            )
        )

    @staticmethod
    def _plan_summary(plan: AgentPlan) -> str:
        first_step = plan.steps[0].title if plan.steps else "No steps"
        return f"I will plan and execute this task for {plan.business_code}. First step: {first_step}. Total steps: {len(plan.steps)}."

    def _snapshot_event(self, session_id: str, run_id: str) -> AgentStreamEvent:
        messages = self.session_repository.list_messages(session_id)
        tasks = self.task_service.list_session_tasks(session_id)
        runs = self.session_repository.list_runs(session_id)
        return self._event(
            "session_snapshot",
            session_id,
            run_id,
            {
                "session_id": session_id,
                "messages": [message.model_dump(mode="json") for message in messages],
                "tasks": [task.model_dump(mode="json") for task in tasks],
                "runs": [run.model_dump(mode="json") for run in runs],
            },
        )

    @staticmethod
    def _event(event_name: str, session_id: str, run_id: str, data: dict) -> AgentStreamEvent:
        return AgentStreamEvent(
            event=event_name,
            session_id=session_id,
            run_id=run_id,
            data=data,
            timestamp=event_timestamp(),
        )
