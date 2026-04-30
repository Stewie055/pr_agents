from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
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
    TaskResponse,
)

from .context import ContextManager

if TYPE_CHECKING:
    from pydantic_ai.models import Model

    from pr_agents.application.tasks import TaskApplicationService
    from pr_agents.infrastructure import AgentSessionRepository


def event_timestamp() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class AgentDeps:
    session_id: str
    run_id: str
    task_service: TaskApplicationService
    session_repository: AgentSessionRepository
    context: AgentContext
    queue: asyncio.Queue[AgentStreamEvent]
    mode: str
    active_mode: str
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
        fallback_agent_model: Model | None,
        mode: str,
    ) -> None:
        self.session_repository = session_repository
        self.task_service = task_service
        self.context_manager = context_manager
        self._mode = mode
        self.agent = self._build_agent(agent_model, "pr_agents_runtime")
        self.fallback_agent = (
            self._build_agent(fallback_agent_model, "pr_agents_runtime_fallback")
            if fallback_agent_model is not None
            else None
        )

    @property
    def mode(self) -> str:
        return self._mode

    def _build_agent(self, agent_model: Model, name: str) -> Agent[AgentDeps, str]:
        agent = Agent(
            agent_model,
            deps_type=AgentDeps,
            instructions=self._instructions,
            name=name,
        )
        self._register_tools(agent)
        return agent

    def _register_tools(self, agent: Agent[AgentDeps, str]) -> None:
        @agent.tool
        async def analyze_source(
            ctx: RunContext[AgentDeps],
            objective: str = "",
        ) -> str:
            deps = ctx.deps
            source = deps.context.latest_source
            if not source:
                return await self._clarify_missing_source(
                    deps,
                    "analyze_source",
                    "请先在左侧选择或上传一个 CSV 数据源，或者注册一个 SQL 数据源，然后再发起分析。",
                )
            source_type = source.get("source_type")
            step_id = await deps.start_tool_step(
                "Analyze selected source",
                "analyze_source",
                {
                    "objective": objective or deps.context.user_message,
                    "source_id": source.get("source_id"),
                    "source_type": source_type,
                    "business_code": source.get("metadata", {}).get("business_code"),
                },
            )
            source_record = deps.session_repository.get_source(str(source["source_id"]))
            if source_record is None:
                return await self._clarify_missing_source(deps, "analyze_source", "选择的数据源不存在，请重新选择。")
            response = deps.task_service.submit_source_analysis_async(
                session_id=deps.session_id,
                source=source_record,
                objective=objective or deps.context.user_message,
            )
            await deps.emit(
                "task_queued",
                {"step_id": step_id, "task_id": response.task_id, "status": response.status.value},
            )
            return await self._handle_async_task_response(
                deps,
                step_id,
                response.task_id,
                str(source.get("metadata", {}).get("business_code") or source_type or "analysis"),
                str(source_type or "source"),
            )

        @agent.tool
        async def run_file_analysis_workflow(
            ctx: RunContext[AgentDeps],
            business_code: str = "A_DEMO",
            objective: str = "",
            chart_type: str = "scientific_plot",
            source_pattern: str = "per_business_file",
        ) -> str:
            deps = ctx.deps
            source = deps.context.latest_source
            if not source or source.get("source_type") not in {"file", "csv_file"}:
                return await self._clarify_missing_source(
                    deps,
                    "run_file_analysis_workflow",
                    "请先选择或上传一个 CSV 文件数据源。",
                )
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
            source_record = deps.session_repository.get_source(str(source["source_id"]))
            if source_record is None:
                return await self._clarify_missing_source(deps, "run_file_analysis_workflow", "选择的数据源不存在，请重新选择。")
            response = deps.task_service.submit_source_analysis_async(
                session_id=deps.session_id,
                source=source_record,
                objective=objective or deps.context.user_message,
            )
            await deps.emit("task_queued", {"step_id": step_id, "task_id": response.task_id, "status": response.status.value})
            return await self._handle_async_task_response(deps, step_id, response.task_id, business_code, "csv_file")

        @agent.tool
        async def run_db_analysis_workflow(
            ctx: RunContext[AgentDeps],
            business_code: str = "A_DEMO",
            objective: str = "",
            chart_type: str = "scientific_plot",
        ) -> str:
            deps = ctx.deps
            source = deps.context.latest_source
            if not source or source.get("source_type") not in {"database", "sql_query"}:
                return await self._clarify_missing_source(
                    deps,
                    "run_db_analysis_workflow",
                    "请先选择或注册一个 SQL 数据源。",
                )
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
            source_record = deps.session_repository.get_source(str(source["source_id"]))
            if source_record is None:
                return await self._clarify_missing_source(deps, "run_db_analysis_workflow", "选择的数据源不存在，请重新选择。")
            response = deps.task_service.submit_source_analysis_async(
                session_id=deps.session_id,
                source=source_record,
                objective=objective or deps.context.user_message,
            )
            await deps.emit("task_queued", {"step_id": step_id, "task_id": response.task_id, "status": response.status.value})
            return await self._handle_async_task_response(deps, step_id, response.task_id, business_code, "sql_query")

        @agent.tool
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

        @agent.tool
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

        @agent.tool
        async def cancel_task(ctx: RunContext[AgentDeps], task_id: str = "") -> str:
            deps = ctx.deps
            target_task_id = task_id or deps.latest_task_id or ""
            step_id = await deps.start_tool_step("Cancel analysis task", "cancel_task", {"task_id": target_task_id})
            if not target_task_id:
                message = "No task id is available to cancel."
                await deps.complete_tool_step(step_id, observation_summary={"summary": message})
                return message
            response = deps.task_service.cancel_task(target_task_id)
            await deps.complete_tool_step(
                step_id,
                observation_summary=response.model_dump(mode="json"),
                task_id=target_task_id,
                tool_result={"step_id": step_id, **response.model_dump(mode="json")},
            )
            return response.message

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

    async def _handle_async_task_response(
        self,
        deps: AgentDeps,
        step_id: str,
        task_id: str,
        business_code: str,
        source_label: str,
    ) -> str:
        last_status = ""
        while True:
            detail = await asyncio.to_thread(deps.task_service.get_task, task_id)
            if detail is None:
                await deps.fail_tool_step(step_id, "Background task disappeared.", task_id=task_id)
                return "Background task disappeared."
            status = detail.task.status.value
            if status != last_status:
                last_status = status
                await deps.emit(
                    "task_status",
                    {"step_id": step_id, "task_id": task_id, "status": status},
                )
            if status in {"succeeded", "failed", "cancelled"}:
                break
            await asyncio.sleep(0.1)

        detail = await asyncio.to_thread(deps.task_service.get_task, task_id)
        if detail is None:
            await deps.fail_tool_step(step_id, "Background task disappeared.", task_id=task_id)
            return "Background task disappeared."
        if detail.task.status.value == "cancelled":
            message = "Analysis task was cancelled."
            await deps.fail_tool_step(step_id, message, task_id=task_id)
            return message
        if detail.task.status.value == "failed" or not detail.result:
            message = detail.task.error_summary.get("message", "Analysis task failed.")
            await deps.fail_tool_step(step_id, message, task_id=task_id)
            return message

        response = TaskResponse(
            task_id=task_id,
            session_id=deps.session_id,
            status=detail.task.status,
            result=detail.result,
        )
        await deps.emit(
            "artifacts_ready",
            {
                "step_id": step_id,
                "task_id": task_id,
                "artifacts": [artifact.model_dump(mode="json") for artifact in detail.artifacts],
            },
        )
        return await self._handle_task_response(deps, step_id, response, business_code, source_label)

    async def _fail_missing_source(self, deps: AgentDeps, tool_name: str, message: str) -> str:
        step_id = await deps.start_tool_step(
            f"Resolve source for {tool_name}",
            tool_name,
            {"source": deps.context.latest_source or "missing"},
        )
        await deps.fail_tool_step(step_id, message)
        return message

    async def _clarify_missing_source(self, deps: AgentDeps, tool_name: str, message: str) -> str:
        step_id = await deps.start_tool_step(
            f"Clarify source for {tool_name}",
            tool_name,
            {"source": deps.context.latest_source or "missing"},
        )
        await deps.complete_tool_step(
            step_id,
            observation_summary={"summary": message, "state": "clarification_required"},
            tool_result={"step_id": step_id, "status": "clarification_required", "message": message},
        )
        return message

    async def _run_with_fallback(self, request_content: str, deps: AgentDeps, event_handler) -> Any:
        if deps.mode == "fake" and self.fallback_agent is not None:
            deps.active_mode = "fake"
            return await self.fallback_agent.run(
                request_content,
                deps=deps,
                event_stream_handler=event_handler,
            )
        try:
            return await self.agent.run(
                request_content,
                deps=deps,
                event_stream_handler=event_handler,
            )
        except Exception as exc:
            if (
                self.fallback_agent is None
                or deps.current_step_ids
                or deps.assistant_started
                or deps.mode != "llm"
            ):
                raise
            deps.active_mode = "fake"
            self.session_repository.update_run(
                deps.run_id,
                AgentRunStatus.RUNNING,
                metadata={
                    "model_mode_used": "fake",
                    "used_fallback": True,
                    "fallback_reason": str(exc),
                },
            )
            await deps.emit(
                "model_fallback",
                {"requested_mode": deps.mode, "active_mode": "fake", "reason": str(exc)},
            )
            return await self.fallback_agent.run(
                request_content,
                deps=deps,
                event_stream_handler=event_handler,
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
        request_source_id = run.metadata.get("source_id")
        requested_mode = run.metadata.get("requested_model_mode", self.mode)
        if requested_mode not in {"fake", "llm"}:
            requested_mode = self.mode
        if requested_mode == "llm" and self.mode == "fake":
            requested_mode = "fake"
        self.session_repository.update_run(
            run_id,
            AgentRunStatus.RUNNING,
            summary="Run started.",
            metadata={
                "state": "running",
                "model_mode_requested": requested_mode,
                "model_mode_used": requested_mode,
                "used_fallback": False,
            },
        )
        context = self.context_manager.build_context(session_id, request_content, request_source_id)
        queue: asyncio.Queue[AgentStreamEvent] = asyncio.Queue()
        deps = AgentDeps(
            session_id=session_id,
            run_id=run_id,
            task_service=self.task_service,
            session_repository=self.session_repository,
            context=context,
            queue=queue,
            mode=requested_mode,
            active_mode=requested_mode,
            latest_report_text=context.latest_report_text,
            latest_report_artifact_id=context.latest_report_artifact_id,
        )
        debug_metadata = {
            "prompt_snapshot": {
                "system_prompt": self._instructions_from_context(context),
                "user_goal": request_content,
                "conversation_window": context.model_dump(mode="json")["conversation_window"],
                "recent_tasks": context.model_dump(mode="json")["recent_tasks"],
                "recent_artifacts": context.model_dump(mode="json")["recent_artifacts"],
            },
            "memory_snapshot": context.memory.model_dump(mode="json"),
            "context_summary": {
                "latest_report_summary": context.latest_report_summary,
                "latest_report_artifact_id": context.latest_report_artifact_id,
                "recent_message_count": len(context.conversation_window),
                "recent_task_count": len(context.recent_tasks),
            },
        }
        self.session_repository.update_run(
            run_id,
            AgentRunStatus.RUNNING,
            summary="Run started.",
            metadata=debug_metadata,
        )
        yield self._event(
            "run_started",
            session_id,
            run_id,
            {
                "goal": request_content,
                "intent_mode": requested_mode,
                "source_id": request_source_id,
                "debug": debug_metadata,
            },
        )

        async def event_handler(_run_ctx: RunContext[AgentDeps], stream) -> None:
            async for event in stream:
                if isinstance(event, PartStartEvent) and isinstance(event.part, TextPart):
                    await deps.append_assistant_text(event.part.content)
                elif isinstance(event, PartDeltaEvent) and isinstance(event.delta, TextPartDelta):
                    await deps.append_assistant_text(event.delta.content_delta)

        async def run_agent() -> None:
            try:
                result = await self._run_with_fallback(request_content, deps, event_handler)
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
                        "intent_mode": deps.active_mode,
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
        return AgentRuntime._instructions_from_context(ctx.deps.context)

    @staticmethod
    def _instructions_from_context(context: AgentContext) -> str:
        latest_task = context.memory.mid_term.latest_task_summary
        return (
            "You are a concise data analysis agent. "
            "Reply directly for normal conversation. "
            "Use tools when the user asks you to run a file analysis, run a database analysis, show the latest report, or summarize the latest report. "
            "Only run analysis tools when a matching session source is available. If no file or database source is registered, tell the user to register one or use a demo source first. "
            "When a tool is needed, do not send any explanatory preamble before calling the tool. Call the tool first. "
            "After all required tools finish, provide one concise final answer in the user's language without exposing internal implementation details. "
            "Do not call load_latest_report after a successful analysis unless the user explicitly asks to see the report text. "
            f"available_source_count={len(context.available_sources)}; "
            f"latest_source_type={(context.latest_source or {}).get('source_type', 'none')}; "
            f"Session context: latest_report_available={bool(context.latest_report_artifact_id)}; "
            f"latest_report_summary={context.latest_report_summary or 'none'}; "
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
