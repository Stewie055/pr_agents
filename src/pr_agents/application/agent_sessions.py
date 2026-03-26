from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pr_agents.agent.intents import FakeIntentParser, IntentParser
from pr_agents.agent.runtime import ConversationRouter, FakePlanner, Planner
from pr_agents.application.tasks import TaskApplicationService
from pr_agents.infrastructure import AgentSessionRepository
from pr_agents.models import (
    AgentAction,
    AgentEntry,
    AgentMessageStartResponse,
    AgentRun,
    AgentRunStatus,
    AgentSessionResponse,
    AgentStepStatus,
    AgentStreamEvent,
    AgentUserMessageRequest,
    CreateAgentSessionResponse,
    DatabaseAnalysisRequest,
    FileAnalysisRequest,
    MessageRole,
    MessageType,
)


def event_timestamp() -> str:
    return datetime.now(UTC).isoformat()


class AgentSessionService:
    def __init__(
        self,
        session_repository: AgentSessionRepository,
        task_service: TaskApplicationService,
        demo_data_path: str,
        intent_parser: IntentParser,
        router: ConversationRouter,
        planner: Planner,
    ) -> None:
        self.session_repository = session_repository
        self.task_service = task_service
        self.demo_data_path = Path(demo_data_path)
        self.intent_parser = intent_parser
        self.router = router
        self.planner = planner
        self._pending_events: list[AgentStreamEvent] = []

    @property
    def intent_mode(self) -> str:
        return self.intent_parser.mode.value

    def create_session(self) -> CreateAgentSessionResponse:
        session_id = f"session-{uuid4().hex[:8]}"
        self.session_repository.create_session(session_id)
        self.session_repository.add_message(
            session_id,
            MessageRole.ASSISTANT,
            MessageType.CHAT,
            "Agent session created. Ask me to analyze demo data, generate charts, or produce a report.",
        )
        return CreateAgentSessionResponse(session_id=session_id)

    def get_session(self, session_id: str) -> AgentSessionResponse:
        self.session_repository.create_session(session_id)
        return AgentSessionResponse(
            session_id=session_id,
            messages=self.session_repository.list_messages(session_id),
            tasks=self.task_service.list_session_tasks(session_id),
            runs=self.session_repository.list_runs(session_id),
        )

    def start_message_run(self, session_id: str, request: AgentUserMessageRequest) -> AgentMessageStartResponse:
        self.session_repository.create_session(session_id)
        message = self.session_repository.add_message(
            session_id,
            MessageRole.USER,
            MessageType.CHAT,
            request.content,
        )
        run = self.session_repository.create_run(
            session_id=session_id,
            goal=request.content,
            intent_mode=self.intent_mode,
            metadata={
                "request_content": request.content,
                "message_id": message.message_id,
                "state": "queued",
            },
        )
        return AgentMessageStartResponse(
            session_id=session_id,
            run_id=run.run_id,
            message_id=message.message_id,
            stream_url=f"/api/v1/agent/sessions/{session_id}/runs/{run.run_id}/stream",
        )

    def stream_run_events(self, session_id: str, run_id: str):
        run = self.session_repository.get_run(run_id)
        if run is None or run.session_id != session_id:
            yield self._event("run_failed", session_id, run_id, {"message": "run not found"})
            return
        if run.status != AgentRunStatus.PLANNED:
            yield self._event(
                "session_snapshot",
                session_id,
                run_id,
                self.get_session(session_id).model_dump(mode="json"),
            )
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
            {"goal": request_content, "intent_mode": self.intent_mode},
        )

        quick_action = self.router.route(request_content)
        is_task_candidate = quick_action is None
        if quick_action == AgentAction.CHAT:
            yield from self._stream_chat_reply(session_id, run_id, request_content)
            return
        if quick_action == AgentAction.SHOW_REPORT:
            yield from self._stream_report_follow_up(session_id, run_id, request_content)
            return

        yield self._event("routing_started", session_id, run_id, {"goal": request_content})
        fast_path = is_task_candidate and self.router.is_explicit_task(request_content)
        if fast_path:
            yield self._event("fast_path_selected", session_id, run_id, {"reason": "explicit_task_pattern"})
            intent = FakeIntentParser().parse(request_content)
            planner = FakePlanner()
        else:
            intent = self.intent_parser.parse(request_content)
            planner = self.planner
        if is_task_candidate and intent.action != AgentAction.ANALYZE:
            intent = FakeIntentParser().parse(request_content)
            planner = FakePlanner()

        if intent.action == AgentAction.CHAT:
            yield from self._stream_chat_reply(
                session_id,
                run_id,
                request_content,
                metadata={
                    "intent_source": intent.intent_source,
                    "intent_mode": self.intent_mode,
                    "intent_fallback": intent.used_fallback,
                },
            )
            return

        if intent.action == AgentAction.SHOW_REPORT:
            yield from self._stream_report_follow_up(session_id, run_id, request_content)
            return

        yield self._event(
            "planning_started",
            session_id,
            run_id,
            {"intent_mode": self.intent_mode, "fast_path": fast_path},
        )
        plan = planner.build_plan(intent)
        self.session_repository.update_run(
            run_id,
            AgentRunStatus.RUNNING,
            summary=f"Created plan with {len(plan.steps)} steps.",
            metadata={
                "business_code": intent.business_code,
                "entry": intent.entry.value,
                "intent_source": intent.intent_source,
                "intent_fallback": intent.used_fallback,
                "planner_source": plan.planner_source,
                "goal": plan.goal,
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
            self._plan_summary(intent.business_code, plan.steps[0].title if plan.steps else "No steps", len(plan.steps)),
            metadata={
                "run_id": run_id,
                "business_code": intent.business_code,
                "entry": intent.entry.value,
                "intent_source": intent.intent_source,
                "intent_mode": self.intent_mode,
                "intent_fallback": intent.used_fallback,
                "planner_source": plan.planner_source,
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

        final_payload, failed, execution_events = self._execute_plan(session_id, run_id, intent, steps)
        for event in execution_events:
            yield event
        event_name = "run_failed" if failed else "run_completed"
        yield self._event(event_name, session_id, run_id, final_payload)
        yield self._event(
            "session_snapshot",
            session_id,
            run_id,
            self.get_session(session_id).model_dump(mode="json"),
        )

    def handle_message(self, session_id: str, request: AgentUserMessageRequest) -> AgentSessionResponse:
        start = self.start_message_run(session_id, request)
        self._pending_events = []
        for _ in self.stream_run_events(session_id, start.run_id):
            pass
        return self.get_session(session_id)

    def read_session_artifact_content(self, session_id: str, artifact_id: str) -> str | None:
        task_ids = {task.task_id for task in self.task_service.list_session_tasks(session_id)}
        artifact = self.task_service.get_artifact(artifact_id)
        if artifact is None or artifact.task_id not in task_ids:
            return None
        return self.task_service.read_artifact_content(artifact_id)

    def _stream_chat_reply(self, session_id: str, run_id: str, content: str, metadata: dict | None = None):
        reply = self._chat_reply_text(content)
        message = self.session_repository.add_message(
            session_id,
            MessageRole.ASSISTANT,
            MessageType.CHAT,
            reply,
            metadata=metadata or {"chat_only": True, "intent_mode": self.intent_mode},
        )
        self.session_repository.update_run(
            run_id,
            AgentRunStatus.SUCCEEDED,
            summary="Returned direct chat reply.",
            metadata={"chat_only": True, "message_id": message.message_id},
        )
        yield self._event("chat_reply", session_id, run_id, {"message": reply, "message_id": message.message_id})
        yield self._event("run_completed", session_id, run_id, {"summary": "Returned direct chat reply."})
        yield self._event(
            "session_snapshot",
            session_id,
            run_id,
            self.get_session(session_id).model_dump(mode="json"),
        )

    def _stream_report_follow_up(self, session_id: str, run_id: str, content: str):
        tasks = self.task_service.list_session_tasks(session_id)
        if not tasks:
            self.session_repository.add_message(
                session_id,
                MessageRole.ASSISTANT,
                MessageType.ERROR,
                "There is no completed task in this session yet. Run the demo first.",
            )
            self.session_repository.update_run(run_id, AgentRunStatus.FAILED, summary="No completed report available.")
            yield self._event(
                "run_failed",
                session_id,
                run_id,
                {"message": "There is no completed task in this session yet. Run the demo first."},
            )
            yield self._event(
                "session_snapshot",
                session_id,
                run_id,
                self.get_session(session_id).model_dump(mode="json"),
            )
            return
        latest_task = tasks[-1]
        detail = self.task_service.get_task(latest_task.task_id)
        report_artifact = (
            next((a for a in detail.artifacts if a.artifact_type.value == "report"), None) if detail else None
        )
        if detail is None or report_artifact is None:
            self.session_repository.add_message(
                session_id,
                MessageRole.ASSISTANT,
                MessageType.ERROR,
                "The latest task does not have a report artifact.",
            )
            self.session_repository.update_run(run_id, AgentRunStatus.FAILED, summary="Report artifact not found.")
            yield self._event("run_failed", session_id, run_id, {"message": "Report artifact not found."})
            yield self._event(
                "session_snapshot",
                session_id,
                run_id,
                self.get_session(session_id).model_dump(mode="json"),
            )
            return
        report_text = self.task_service.read_artifact_content(report_artifact.artifact_id) or ""
        summary_only = self._is_report_summary_request(content)
        if summary_only:
            chart_type = detail.result.chart.chart_type if detail and detail.result and detail.result.chart else "n/a"
            report_summary = detail.result.report.summary if detail and detail.result and detail.result.report else "n/a"
            business_code = latest_task.input_summary.get("business_code", "A_DEMO")
            response_text = (
                f"Summary for {business_code}: {report_summary} "
                f"Chart type: {chart_type}. The report is available if you want the full text."
            )
            run_summary = "Returned latest report summary."
        else:
            response_text = report_text
            run_summary = "Returned latest report."
        message = self.session_repository.add_message(
            session_id,
            MessageRole.ASSISTANT,
            MessageType.CHAT,
            response_text,
            metadata={
                "task_id": latest_task.task_id,
                "report_artifact_id": report_artifact.artifact_id,
                "report_preview": report_text,
                "summary_only": summary_only,
            },
        )
        self.session_repository.update_run(
            run_id,
            AgentRunStatus.SUCCEEDED,
            summary=run_summary,
            metadata={
                "task_id": latest_task.task_id,
                "report_artifact_id": report_artifact.artifact_id,
                "summary_only": summary_only,
            },
        )
        yield self._event(
            "chat_reply",
            session_id,
            run_id,
            {
                "message": response_text,
                "message_id": message.message_id,
                "report_artifact_id": report_artifact.artifact_id,
            },
        )
        yield self._event("run_completed", session_id, run_id, {"summary": run_summary})
        yield self._event(
            "session_snapshot",
            session_id,
            run_id,
            self.get_session(session_id).model_dump(mode="json"),
        )

    def _execute_plan(self, session_id: str, run_id: str, intent, steps) -> tuple[dict, bool, list[AgentStreamEvent]]:
        task_response = None
        result = None
        report_text = ""
        report_artifact_id = None
        events: list[AgentStreamEvent] = []
        for step in steps:
            self.session_repository.update_run_step(step.step_id, AgentStepStatus.RUNNING)
            yield_data = {
                "step_id": step.step_id,
                "step_index": step.step_index,
                "title": step.title,
                "tool_name": step.tool_name,
            }
            events.append(self._event("step_started", session_id, run_id, yield_data))
            if step.tool_name in {"run_file_analysis_workflow", "run_db_analysis_workflow"}:
                tool_name = "run_db_analysis" if intent.entry == AgentEntry.DATABASE else "run_file_analysis"
                self.session_repository.add_message(
                    session_id,
                    MessageRole.TOOL,
                    MessageType.TOOL_CALL,
                    tool_name,
                    metadata={
                        "run_id": run_id,
                        "step_id": step.step_id,
                        "business_code": intent.business_code,
                        "intent_source": intent.intent_source,
                        "intent_mode": self.intent_mode,
                    },
                )
                events.append(
                    self._event(
                        "tool_called",
                        session_id,
                        run_id,
                        {"step_id": step.step_id, "tool_name": tool_name, "business_code": intent.business_code},
                    )
                )
                task_response = self._run_task(session_id, intent)
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
                            {
                                "step_id": step.step_id,
                                "title": step.title,
                                "message": task_response.error.message,
                            },
                        )
                    )
                    self.session_repository.add_message(
                        session_id,
                        MessageRole.ASSISTANT,
                        MessageType.ERROR,
                        f"Execution stopped at '{step.title}': {task_response.error.message}",
                        metadata={"run_id": run_id, "task_id": task_response.task_id},
                    )
                    return {
                        "message": f"Execution stopped at '{step.title}': {task_response.error.message}",
                        "task_id": task_response.task_id,
                    }, True, events
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
                        "session_id": task_response.session_id,
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
                        {
                            "step_id": step.step_id,
                            "title": step.title,
                            "task_id": task_response.task_id,
                        },
                    )
                )
            else:
                summary = (
                    f"Completed {intent.business_code}. "
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

        source_label = "database analysis" if intent.entry == AgentEntry.DATABASE else "file analysis"
        final_content = (
            f"Completed {source_label} for {intent.business_code}. "
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
                "business_code": intent.business_code,
                "intent_source": intent.intent_source,
                "intent_mode": self.intent_mode,
                "intent_fallback": intent.used_fallback,
                "report_preview": report_text,
            },
        )
        self.session_repository.update_run(
            run_id,
            AgentRunStatus.SUCCEEDED,
            summary=f"Completed {len(steps)} planned steps.",
        )
        return {
            "message": final_content,
            "task_id": task_response.task_id if task_response else None,
            "report_artifact_id": report_artifact_id,
            "summary": f"Completed {len(steps)} planned steps.",
        }, False, events

    def _run_task(self, session_id: str, intent):
        if intent.entry == AgentEntry.DATABASE:
            return self.task_service.submit_db_analysis(
                DatabaseAnalysisRequest(
                    business_code=intent.business_code,
                    objective=intent.objective,
                    query_name="demo_query",
                    sql="select * from cleaned_demo_data",
                    source_profile={"source_pattern": intent.source_pattern.value, "data_version": "demo-v1"},
                    chart_profile={"chart_type": intent.chart_type},
                    report_profile={"template": "demo-template"},
                    session_id=session_id,
                )
            )
        return self.task_service.submit_file_analysis(
            FileAnalysisRequest(
                business_code=intent.business_code,
                objective=intent.objective,
                file_name=self.demo_data_path.name,
                content=self.demo_data_path.read_text(encoding="utf-8"),
                source_profile={"source_pattern": intent.source_pattern.value, "data_version": "demo-v1"},
                chart_profile={"chart_type": intent.chart_type},
                report_profile={"template": "demo-template"},
                session_id=session_id,
            )
        )

    @staticmethod
    def _chat_reply_text(content: str) -> str:
        normalized = content.strip().lower()
        if normalized in {"hi", "hello", "hey", "你好", "您好", "嗨", "在吗"}:
            return (
                "你好。我可以帮你分析 demo 数据、生成科学绘图和报告。"
                "你可以直接说：请用 A_DEMO 生成科学绘图和报告。"
            )
        if "你是谁" in content or "你能做什么" in content or "怎么用" in content or normalized == "help":
            return (
                "我是一个任务型分析 Agent。默认先对话，只有在你明确要求分析数据、生成图表或查看报告时，"
                "我才会规划步骤并调用工具。"
            )
        return "我先不调用工具。你可以直接告诉我要分析哪个业务，比如：请用 A_DEMO 文件数据生成科学绘图和报告。"

    @staticmethod
    def _is_report_summary_request(content: str) -> bool:
        lower = content.lower()
        return (
            "summarize the report" in lower
            or "summarise the report" in lower
            or "report summary" in lower
            or "key points" in lower
            or "概括这份报告" in content
            or "总结这份报告" in content
            or "报告重点" in content
        )

    @staticmethod
    def _plan_summary(business_code: str, first_step: str, step_count: int) -> str:
        return f"I will plan and execute this task for {business_code}. First step: {first_step}. Total steps: {step_count}."

    @staticmethod
    def _event(event_name: str, session_id: str, run_id: str, data: dict) -> AgentStreamEvent:
        return AgentStreamEvent(
            event=event_name,
            session_id=session_id,
            run_id=run_id,
            data=data,
            timestamp=event_timestamp(),
        )

    def iter_formatted_sse(self, session_id: str, run_id: str):
        for event in self.stream_run_events(session_id, run_id):
            yield self._format_event(event)
        yield self._format_event(
            self._event("keepalive", session_id, run_id, {"status": "stream_closed"})
        )

    @staticmethod
    def _format_event(event: AgentStreamEvent) -> str:
        return f"event: {event.event}\ndata: {json.dumps(event.model_dump(mode='json'), ensure_ascii=False)}\n\n"
