from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import PartDeltaEvent, PartStartEvent, TextPart, TextPartDelta

from pr_agents.models import (
    AgentContext,
    AgentRunStatus,
    AgentStepStatus,
    AgentStreamEvent,
    DatabaseAnalysisRequest,
    FileAnalysisRequest,
    MessageRole,
    MessageType,
)

from .context import ContextManager

if TYPE_CHECKING:
    from pydantic_ai.models import Model

    from pr_agents.application.tasks import TaskApplicationService
    from pr_agents.infrastructure import AgentSessionRepository
    from pr_agents.models import TaskResponse


def event_timestamp() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class AgentDeps:
    session_id: str
    run_id: str
    task_service: TaskApplicationService
    session_repository: AgentSessionRepository
    context: AgentContext
    demo_data_path: Path
    queue: asyncio.Queue[AgentStreamEvent]
    mode: str
    latest_report_text: str = ""
    latest_report_artifact_id: str | None = None
    latest_task_id: str | None = None
    latest_business_code: str | None = None
    assistant_text: str = ""
    assistant_started: bool = False
    failed: bool = False
    step_index: int = 0
    report_preview: str = ""
    current_step_ids: list[str] = field(default_factory=list)
    last_tool_name: str | None = None
    pending_preamble: str = ""
    tool_phase_started: bool = False

    async def emit(self, event_name: str, data: dict[str, Any]) -> None:
        await self.queue.put(
            AgentStreamEvent(
                event=event_name,
                session_id=self.session_id,
                run_id=self.run_id,
                data=data,
                timestamp=event_timestamp(),
            )
        )

    async def append_assistant_text(self, chunk: str) -> None:
        if not chunk:
            return
        if not self.tool_phase_started and not self.current_step_ids:
            self.pending_preamble += chunk
            return
        if not self.assistant_started:
            self.assistant_started = True
            await self.emit("assistant_started", {"mode": "stream"})
        self.assistant_text += chunk
        await self.emit("assistant_delta", {"delta": chunk})

    async def start_tool_step(self, title: str, tool_name: str, inputs_summary: dict[str, Any]) -> str:
        self.tool_phase_started = True
        self.pending_preamble = ""
        step = self.session_repository.create_run_step(
            run_id=self.run_id,
            step_index=self.step_index,
            title=title,
            tool_name=tool_name,
            inputs_summary=inputs_summary,
        )
        self.step_index += 1
        self.current_step_ids.append(step.step_id)
        self.session_repository.update_run_step(step.step_id, AgentStepStatus.RUNNING)
        self.last_tool_name = tool_name
        await self.emit(
            "step_started",
            {
                "step_id": step.step_id,
                "step_index": step.step_index,
                "title": title,
                "tool_name": tool_name,
            },
        )
        await self.emit(
            "tool_called",
            {
                "step_id": step.step_id,
                "tool_name": tool_name,
                "inputs": inputs_summary,
            },
        )
        return step.step_id

    async def complete_tool_step(
        self,
        step_id: str,
        *,
        observation_summary: dict[str, Any],
        task_id: str | None = None,
        artifact_ids: list[str] | None = None,
        tool_result: dict[str, Any] | None = None,
    ) -> None:
        self.session_repository.update_run_step(
            step_id,
            AgentStepStatus.SUCCEEDED,
            observation_summary=observation_summary,
            task_id=task_id,
            artifact_ids=artifact_ids or [],
        )
        await self.emit(
            "tool_result",
            {"step_id": step_id, **(tool_result or observation_summary)},
        )
        await self.emit(
            "step_completed",
            {
                "step_id": step_id,
                "summary": observation_summary.get("summary")
                or observation_summary.get("report_summary")
                or observation_summary.get("task_status", "completed"),
                "task_id": task_id,
            },
        )

    async def fail_tool_step(self, step_id: str, message: str, *, task_id: str | None = None) -> None:
        self.failed = True
        self.session_repository.update_run_step(
            step_id,
            AgentStepStatus.FAILED,
            error_summary={"message": message},
            task_id=task_id,
        )
        await self.emit("tool_result", {"step_id": step_id, "status": "failed", "message": message, "task_id": task_id})
        await self.emit("step_failed", {"step_id": step_id, "message": message, "task_id": task_id})


class AgentRuntime:
    def __init__(
        self,
        *,
        session_repository: AgentSessionRepository,
        task_service: TaskApplicationService,
        context_manager: ContextManager,
        agent_model: Model,
        demo_data_path: Path,
        mode: str,
    ) -> None:
        self.session_repository = session_repository
        self.task_service = task_service
        self.context_manager = context_manager
        self.demo_data_path = demo_data_path
        self._mode = mode
        self.agent = Agent(
            agent_model,
            deps_type=AgentDeps,
            instructions=self._instructions,
            name="pr_agents_runtime",
        )
        self._register_tools()

    @property
    def mode(self) -> str:
        return self._mode

    def _register_tools(self) -> None:
        @self.agent.tool
        async def run_file_analysis_workflow(
            ctx: RunContext[AgentDeps],
            business_code: str = "A_DEMO",
            objective: str = "",
            chart_type: str = "scientific_plot",
            source_pattern: str = "per_business_file",
        ) -> str:
            deps = ctx.deps
            title = f"Run file analysis workflow for {business_code}"
            step_id = await deps.start_tool_step(
                title,
                "run_file_analysis_workflow",
                {
                    "business_code": business_code,
                    "objective": objective or deps.context.user_message,
                    "chart_type": chart_type,
                    "source_pattern": source_pattern,
                },
            )
            response = deps.task_service.submit_file_analysis(
                FileAnalysisRequest(
                    business_code=business_code,
                    objective=objective or deps.context.user_message,
                    file_name=deps.demo_data_path.name,
                    content=deps.demo_data_path.read_text(encoding="utf-8"),
                    source_profile={"source_pattern": source_pattern, "data_version": "demo-v1"},
                    chart_profile={"chart_type": chart_type},
                    report_profile={"template": "demo-template"},
                    session_id=deps.session_id,
                )
            )
            return await self._handle_task_response(deps, step_id, response, business_code, "file")

        @self.agent.tool
        async def run_db_analysis_workflow(
            ctx: RunContext[AgentDeps],
            business_code: str = "A_DEMO",
            objective: str = "",
            chart_type: str = "scientific_plot",
        ) -> str:
            deps = ctx.deps
            title = f"Run database analysis workflow for {business_code}"
            step_id = await deps.start_tool_step(
                title,
                "run_db_analysis_workflow",
                {
                    "business_code": business_code,
                    "objective": objective or deps.context.user_message,
                    "chart_type": chart_type,
                },
            )
            response = deps.task_service.submit_db_analysis(
                DatabaseAnalysisRequest(
                    business_code=business_code,
                    objective=objective or deps.context.user_message,
                    query_name="demo_query",
                    sql="select * from cleaned_demo_data",
                    source_profile={"source_pattern": "per_business_file", "data_version": "demo-v1"},
                    chart_profile={"chart_type": chart_type},
                    report_profile={"template": "demo-template"},
                    session_id=deps.session_id,
                )
            )
            return await self._handle_task_response(deps, step_id, response, business_code, "database")

        @self.agent.tool
        async def load_latest_report(ctx: RunContext[AgentDeps]) -> str:
            deps = ctx.deps
            step_id = await deps.start_tool_step("Load latest report", "load_latest_report", {})
            report_text = deps.latest_report_text or deps.context.latest_report_text
            artifact_id = deps.latest_report_artifact_id or deps.context.latest_report_artifact_id
            if not report_text:
                message = "There is no completed report in this session yet."
                await deps.complete_tool_step(
                    step_id,
                    observation_summary={"summary": message},
                    tool_result={"step_id": step_id, "status": "empty"},
                )
                return message
            deps.report_preview = report_text
            await deps.complete_tool_step(
                step_id,
                observation_summary={"summary": "Loaded latest report."},
                artifact_ids=[artifact_id] if artifact_id else [],
                tool_result={"step_id": step_id, "status": "succeeded", "report_artifact_id": artifact_id},
            )
            return report_text

        @self.agent.tool
        async def summarize_report(ctx: RunContext[AgentDeps]) -> str:
            deps = ctx.deps
            step_id = await deps.start_tool_step("Summarize latest report", "summarize_report", {})
            if not deps.report_preview:
                deps.report_preview = deps.latest_report_text or deps.context.latest_report_text
            summary = deps.context.latest_report_summary or "There is no completed report in this session yet."
            business_code = (
                deps.latest_business_code
                or deps.context.memory.mid_term.latest_task_summary.get("business_code")
                or "A_DEMO"
            )
            message = f"Summary for {business_code}: {summary}"
            await deps.complete_tool_step(
                step_id,
                observation_summary={"summary": message},
                artifact_ids=[deps.latest_report_artifact_id] if deps.latest_report_artifact_id else [],
                tool_result={"step_id": step_id, "status": "succeeded", "report_artifact_id": deps.latest_report_artifact_id},
            )
            return message

    async def _handle_task_response(
        self,
        deps: AgentDeps,
        step_id: str,
        response: TaskResponse,
        business_code: str,
        source_label: str,
    ) -> str:
        if response.error or not response.result:
            message = response.error.message if response.error else f"{source_label.title()} analysis failed."
            await deps.fail_tool_step(step_id, message, task_id=response.task_id)
            return message
        result = response.result
        report_artifact_id = result.report.artifact.artifact_id if result.report else None
        report_text = deps.task_service.read_artifact_content(report_artifact_id) or "" if report_artifact_id else ""
        deps.latest_report_text = report_text
        deps.latest_report_artifact_id = report_artifact_id
        deps.latest_task_id = response.task_id
        deps.latest_business_code = business_code
        deps.report_preview = report_text
        self.session_repository.update_run(
            deps.run_id,
            AgentRunStatus.RUNNING,
            metadata={"business_code": business_code, "entry": source_label, "task_type": "analysis"},
        )
        await deps.complete_tool_step(
            step_id,
            observation_summary={
                "task_status": response.status.value,
                "chart_type": result.chart.chart_type if result.chart else None,
                "report_summary": result.report.summary if result.report else None,
            },
            task_id=response.task_id,
            artifact_ids=[artifact.artifact_id for artifact in result.artifacts],
            tool_result={
                "step_id": step_id,
                "task_id": response.task_id,
                "status": response.status.value,
                "chart_type": result.chart.chart_type if result.chart else None,
                "report_artifact_id": report_artifact_id,
            },
        )
        return (
            f"Completed {source_label} analysis for {business_code}. "
            f"Chart type: {result.chart.chart_type if result.chart else 'n/a'}. "
            f"Report summary: {result.report.summary if result.report else 'n/a'}."
        )

    async def stream_run_events(self, session_id: str, run_id: str):
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
        yield self._event("run_started", session_id, run_id, {"goal": request_content, "intent_mode": self.mode})

        context = self.context_manager.build_context(session_id, request_content)
        queue: asyncio.Queue[AgentStreamEvent] = asyncio.Queue()
        deps = AgentDeps(
            session_id=session_id,
            run_id=run_id,
            task_service=self.task_service,
            session_repository=self.session_repository,
            context=context,
            demo_data_path=self.demo_data_path,
            queue=queue,
            mode=self.mode,
            latest_report_text=context.latest_report_text,
            latest_report_artifact_id=context.latest_report_artifact_id,
        )

        async def event_handler(_run_ctx: RunContext[AgentDeps], stream) -> None:
            async for event in stream:
                if isinstance(event, PartStartEvent) and isinstance(event.part, TextPart):
                    await deps.append_assistant_text(event.part.content)
                elif isinstance(event, PartDeltaEvent) and isinstance(event.delta, TextPartDelta):
                    await deps.append_assistant_text(event.delta.content_delta)

        async def run_agent() -> None:
            try:
                result = await self.agent.run(
                    request_content,
                    deps=deps,
                    event_stream_handler=event_handler,
                )
                if deps.current_step_ids:
                    final_text = deps.assistant_text.strip()
                    if not final_text:
                        final_text = str(result.output).strip()
                else:
                    final_text = (deps.assistant_text or deps.pending_preamble or str(result.output)).strip()
                if final_text and not deps.assistant_started:
                    await deps.emit("assistant_started", {"mode": "single"})
                    await self._emit_text_stream(deps, final_text)
                message = self.session_repository.add_message(
                    session_id,
                    MessageRole.ASSISTANT,
                    MessageType.CHAT,
                    final_text,
                    metadata={
                        "run_id": run_id,
                        "task_id": deps.latest_task_id,
                        "report_artifact_id": deps.latest_report_artifact_id,
                        "report_preview": deps.report_preview,
                        "business_code": deps.latest_business_code,
                        "intent_mode": self.mode,
                        "summary_only": deps.last_tool_name == "summarize_report",
                    },
                )
                await deps.emit(
                    "assistant_completed",
                    {"message": final_text, "message_id": message.message_id, "metadata": message.metadata},
                )
                if deps.failed:
                    self.session_repository.update_run(
                        run_id,
                        AgentRunStatus.FAILED,
                        summary="One or more tools failed during execution.",
                    )
                    await deps.emit("run_failed", {"message": "One or more tools failed during execution."})
                else:
                    summary = (
                        f"Completed {len(deps.current_step_ids)} tool steps."
                        if deps.current_step_ids
                        else "Returned direct agent reply."
                    )
                    self.session_repository.update_run(run_id, AgentRunStatus.SUCCEEDED, summary=summary)
                    await deps.emit(
                        "run_completed",
                        {
                            "message": final_text,
                            "task_id": deps.latest_task_id,
                            "report_artifact_id": deps.latest_report_artifact_id,
                            "summary": summary,
                        },
                    )
            except Exception as exc:
                self.session_repository.add_message(
                    session_id,
                    MessageRole.ASSISTANT,
                    MessageType.ERROR,
                    str(exc),
                    metadata={"run_id": run_id},
                )
                self.session_repository.update_run(run_id, AgentRunStatus.FAILED, summary=str(exc))
                await deps.emit("run_failed", {"message": str(exc)})
            finally:
                await queue.put(self._event("__done__", session_id, run_id, {}))

        task = asyncio.create_task(run_agent())
        try:
            while True:
                event = await queue.get()
                if event.event == "__done__":
                    break
                yield event
        finally:
            await task
        yield self._snapshot_event(session_id, run_id)

    @staticmethod
    def _instructions(ctx: RunContext[AgentDeps]) -> str:
        deps = ctx.deps
        latest_task = deps.context.memory.mid_term.latest_task_summary
        return (
            "You are a concise data analysis agent. "
            "Reply directly for normal conversation. "
            "Use tools when the user asks you to run a file analysis, run a database analysis, show the latest report, or summarize the latest report. "
            "When a tool is needed, do not send any explanatory preamble before calling the tool. Call the tool first. "
            "After all required tools finish, provide one concise final answer in the user's language without exposing internal implementation details. "
            "Do not call load_latest_report after a successful analysis unless the user explicitly asks to see the report text. "
            f"Session context: latest_report_available={bool(deps.context.latest_report_artifact_id)}; "
            f"latest_report_summary={deps.context.latest_report_summary or 'none'}; "
            f"latest_task_business_code={latest_task.get('business_code', 'none')}."
        )

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
    def _event(event_name: str, session_id: str, run_id: str, data: dict[str, Any]) -> AgentStreamEvent:
        return AgentStreamEvent(
            event=event_name,
            session_id=session_id,
            run_id=run_id,
            data=data,
            timestamp=event_timestamp(),
        )

    @staticmethod
    def _chunk_text(content: str, chunk_size: int = 16):
        text = content or ""
        for index in range(0, len(text), chunk_size):
            yield text[index : index + chunk_size]

    async def _emit_text_stream(self, deps: AgentDeps, content: str, delay: float = 0.15) -> None:
        for chunk in self._chunk_text(content):
            await deps.emit("assistant_delta", {"delta": chunk})
            await asyncio.sleep(delay)
