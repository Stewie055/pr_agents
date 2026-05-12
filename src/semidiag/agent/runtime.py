from __future__ import annotations

import json
import re
from collections.abc import Iterator
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from semidiag.agent.llm import LLMError, LLMProvider, StubLLMProvider
from semidiag.agent.memory import MemoryService
from semidiag.agent.router import CaseRouteContext, LLMRouter, RouteDecision, StateGate
from semidiag.domain import AgentMessage, AgentStepTrace, AnalysisArtifact, LLMAuditEvent, ToolCallTrace
from semidiag.infrastructure.metrics import MetricRepository
from semidiag.infrastructure.repository import SQLiteRepository
from semidiag.plugins import GenericEquipmentPlugin, PluginRegistry
from semidiag.plugins.base import DiagnosticPlugin
from semidiag.tools import ToolContext, ToolRegistry, build_default_registry


@dataclass
class AgentTurnResult:
    message: AgentMessage
    artifacts: list[AnalysisArtifact]
    tool_traces: list[ToolCallTrace]
    summary: str


@dataclass
class AgentStreamEvent:
    event: str
    data: dict[str, Any]


@dataclass
class AgentState:
    case_id: str
    user_content: str
    active_dataset_id: str | None
    decision: RouteDecision
    actor: str
    messages: list[dict[str, Any]]
    observations: list[dict[str, Any]]
    step_count: int = 0
    stop_reason: str | None = None


class AgentRuntime:
    max_steps = 6
    max_repeated_tool_calls = 2

    def __init__(
        self,
        repository: SQLiteRepository,
        registry: ToolRegistry | None = None,
        llm: LLMProvider | None = None,
        memory: MemoryService | None = None,
        plugin: DiagnosticPlugin | None = None,
        plugin_registry: PluginRegistry | None = None,
        metric_repository: MetricRepository | None = None,
    ) -> None:
        self.repository = repository
        self.registry = registry or build_default_registry()
        self.llm = llm or StubLLMProvider()
        self.memory = memory or MemoryService()
        self.plugin = plugin or GenericEquipmentPlugin()
        self.plugin_registry = plugin_registry or PluginRegistry([self.plugin])
        self.metric_repository = metric_repository
        self.router = LLMRouter(self.llm)
        self.state_gate = StateGate()

    def handle_user_message(
        self,
        *,
        case_id: str,
        content: str,
        dataset_id: str | None = None,
        actor: str = "engineer",
    ) -> AgentTurnResult:
        case = self.repository.get_case(case_id)
        if case is None:
            raise KeyError(case_id)
        self.repository.add_message(AgentMessage(case_id=case_id, role="user", content=content))

        datasets = self.repository.list_case_datasets(case_id)
        active_dataset_id = dataset_id or (datasets[-1].id if datasets else None)
        route_context = self._build_route_context(case_id=case_id)
        decision = self.router.route(user_content=content, context=route_context)
        gate = self.state_gate.check(decision=decision, context=route_context)
        if not gate.allowed:
            return self._local_reply(
                case_id=case_id,
                content=gate.message or "当前状态不满足执行条件。",
                decision=decision,
                llm_used=not isinstance(self.llm, StubLLMProvider),
                blocked_by_state_gate=True,
            )

        if isinstance(self.llm, StubLLMProvider):
            return self._handle_stub_turn(
                case_id=case_id,
                content=content,
                active_dataset_id=active_dataset_id,
                actor=actor,
                decision=decision,
            )

        if decision.intent in {"chat_response", "knowledge_qa", "clarification", "workflow_request"}:
            return self._handle_non_tool_llm_turn(case_id=case_id, content=content, decision=decision)

        messages = self._build_llm_messages(
            case_id=case_id,
            user_content=content,
            active_dataset_id=active_dataset_id,
            decision=decision,
        )
        return self._run_react_loop(
            AgentState(
                case_id=case_id,
                user_content=content,
                active_dataset_id=active_dataset_id,
                decision=decision,
                actor=actor,
                messages=messages,
                observations=[],
            )
        )

    def stream_user_message(
        self,
        *,
        case_id: str,
        content: str,
        dataset_id: str | None = None,
        actor: str = "engineer",
    ) -> Iterator[AgentStreamEvent]:
        case = self.repository.get_case(case_id)
        if case is None:
            raise KeyError(case_id)
        self.repository.add_message(AgentMessage(case_id=case_id, role="user", content=content))

        datasets = self.repository.list_case_datasets(case_id)
        active_dataset_id = dataset_id or (datasets[-1].id if datasets else None)
        yield AgentStreamEvent(event="started", data={"message": "开始处理请求"})

        route_context = self._build_route_context(case_id=case_id)
        decision = self.router.route(user_content=content, context=route_context)
        yield AgentStreamEvent(
            event="route",
            data={
                "intent": decision.intent,
                "requires_dataset": decision.requires_dataset,
                "user_goal": decision.user_goal,
                "reason": decision.reason,
            },
        )

        gate = self.state_gate.check(decision=decision, context=route_context)
        if not gate.allowed:
            content_out = gate.message or "当前状态不满足执行条件。"
            yield from self._stream_local_reply(
                case_id=case_id,
                content=content_out,
                decision=decision,
                llm_used=not isinstance(self.llm, StubLLMProvider),
                blocked_by_state_gate=True,
            )
            return

        if decision.intent in {"chat_response", "knowledge_qa", "clarification", "workflow_request"}:
            if isinstance(self.llm, StubLLMProvider):
                yield from self._stream_local_reply(
                    case_id=case_id,
                    content=self._stub_non_tool_reply(decision=decision, has_dataset=active_dataset_id is not None),
                    decision=decision,
                    llm_used=False,
                )
                return
            yield from self._stream_non_tool_llm_turn(case_id=case_id, content=content, decision=decision)
            return

        messages = self._build_llm_messages(
            case_id=case_id,
            user_content=content,
            active_dataset_id=active_dataset_id,
            decision=decision,
        )
        yield from self._run_react_loop_stream(
            AgentState(
                case_id=case_id,
                user_content=content,
                active_dataset_id=active_dataset_id,
                decision=decision,
                actor=actor,
                messages=messages,
                observations=[],
            )
        )

    def _run_react_loop(self, state: AgentState) -> AgentTurnResult:
        context = self._tool_context(state)
        tools = self.llm.tool_specs(self.registry)
        call_counts: dict[str, int] = {}
        final_content: str | None = None

        self._record_route_decision(state)

        for step_index in range(1, self.max_steps + 1):
            state.step_count = step_index
            started = perf_counter()
            result = self._call_llm_for_plan(case_id=state.case_id, messages=state.messages, tools=tools)
            duration_ms = int((perf_counter() - started) * 1000)

            if not result.tool_calls:
                final_content = result.content
                state.stop_reason = "final_answer"
                self._record_agent_step(
                    case_id=state.case_id,
                    step_index=step_index,
                    phase="finalize",
                    llm_metadata=self._step_llm_metadata(result.metadata),
                    stop_reason=state.stop_reason,
                    duration_ms=duration_ms,
                )
                break

            assistant_tool_message = self.llm.assistant_plan_message(result)
            state.messages.append(assistant_tool_message)
            tool_observations: list[dict[str, Any]] = []
            observation_messages: list[dict[str, Any]] = []

            for call in result.tool_calls:
                if self.registry.get_tool(call.name) is None:
                    raise LLMError(f"LLM requested unknown tool: {call.name}", status_code=502)
                signature = f"{call.name}:{json.dumps(call.arguments, sort_keys=True, ensure_ascii=False)}"
                call_counts[signature] = call_counts.get(signature, 0) + 1
                if call_counts[signature] > self.max_repeated_tool_calls:
                    state.stop_reason = "repeated_tool_call"
                    final_content = self._repeated_tool_call_message()
                    break

                arguments = self._prepare_tool_arguments(call.name, call.arguments, state.active_dataset_id)
                try:
                    tool_result = self.registry.run(call.name, context, arguments)
                    observation = self._tool_result_observation(call.name, tool_result)
                except Exception as exc:
                    observation = {
                        "tool_name": call.name,
                        "summary": f"Tool {call.name} failed: {exc}",
                        "error": str(exc),
                        "data": {},
                        "artifact_ids": [],
                        "evidence_ids": [],
                        "next_suggestions": self._recovery_suggestions(call.name),
                    }
                tool_observations.append(observation)
                state.observations.append(observation)
                observation_messages.append(
                    {"tool_call_id": call.id, "tool_name": call.name, "observation": observation}
                )

            self._record_agent_step(
                case_id=state.case_id,
                step_index=step_index,
                phase="observe",
                tool_calls=[
                    {"id": call.id, "name": call.name, "arguments": call.arguments}
                    for call in result.tool_calls
                ],
                observations=tool_observations,
                llm_metadata=self._step_llm_metadata(result.metadata),
                stop_reason=state.stop_reason,
                duration_ms=duration_ms,
            )

            state.messages.extend(self.llm.tool_observation_messages(observation_messages))
            if final_content:
                break

        if final_content is None:
            state.stop_reason = state.stop_reason or "max_steps"
            final_content = self._finalize_from_observations(state)

        content_out = self._sanitize_user_visible_text(final_content)
        return self._persist_react_result(state=state, content_out=content_out)

    def _run_react_loop_stream(self, state: AgentState) -> Iterator[AgentStreamEvent]:
        context = self._tool_context(state)
        tools = self.llm.tool_specs(self.registry)
        call_counts: dict[str, int] = {}
        final_content: str | None = None
        streamed_final_content = ""

        self._record_route_decision(state)

        for step_index in range(1, self.max_steps + 1):
            state.step_count = step_index
            started = perf_counter()
            result, deltas = self._call_llm_for_plan_stream(case_id=state.case_id, messages=state.messages, tools=tools)
            duration_ms = int((perf_counter() - started) * 1000)
            for delta in deltas:
                streamed_final_content += delta
                yield AgentStreamEvent(event="message_delta", data={"delta": delta})

            if not result.tool_calls:
                final_content = result.content or streamed_final_content
                state.stop_reason = "final_answer"
                self._record_agent_step(
                    case_id=state.case_id,
                    step_index=step_index,
                    phase="finalize",
                    llm_metadata=self._step_llm_metadata(result.metadata),
                    stop_reason=state.stop_reason,
                    duration_ms=duration_ms,
                )
                break

            assistant_tool_message = self.llm.assistant_plan_message(result)
            state.messages.append(assistant_tool_message)
            tool_observations: list[dict[str, Any]] = []
            observation_messages: list[dict[str, Any]] = []

            for call in result.tool_calls:
                if self.registry.get_tool(call.name) is None:
                    raise LLMError(f"LLM requested unknown tool: {call.name}", status_code=502)
                signature = f"{call.name}:{json.dumps(call.arguments, sort_keys=True, ensure_ascii=False)}"
                call_counts[signature] = call_counts.get(signature, 0) + 1
                if call_counts[signature] > self.max_repeated_tool_calls:
                    state.stop_reason = "repeated_tool_call"
                    final_content = self._repeated_tool_call_message()
                    break

                arguments = self._prepare_tool_arguments(call.name, call.arguments, state.active_dataset_id)
                yield AgentStreamEvent(event="tool_start", data={"tool_name": call.name})
                try:
                    tool_result = self.registry.run(call.name, context, arguments)
                    observation = self._tool_result_observation(call.name, tool_result)
                    yield AgentStreamEvent(
                        event="tool_result",
                        data={
                            "tool_name": call.name,
                            "summary": observation.get("summary") or tool_result.summary,
                            "artifact_ids": observation.get("artifact_ids", []),
                            "evidence_ids": observation.get("evidence_ids", []),
                        },
                    )
                    for artifact in tool_result.artifacts:
                        yield AgentStreamEvent(
                            event="artifact_created",
                            data={
                                "artifact": {
                                    "id": artifact.id,
                                    "kind": artifact.kind,
                                    "title": artifact.title,
                                    "summary": artifact.summary,
                                    "data": artifact.data,
                                }
                            },
                        )
                except Exception as exc:
                    observation = {
                        "tool_name": call.name,
                        "summary": f"Tool {call.name} failed: {exc}",
                        "error": str(exc),
                        "data": {},
                        "artifact_ids": [],
                        "evidence_ids": [],
                        "next_suggestions": self._recovery_suggestions(call.name),
                    }
                    yield AgentStreamEvent(
                        event="tool_result",
                        data={"tool_name": call.name, "summary": observation["summary"], "error": str(exc)},
                    )
                tool_observations.append(observation)
                state.observations.append(observation)
                observation_messages.append(
                    {"tool_call_id": call.id, "tool_name": call.name, "observation": observation}
                )

            self._record_agent_step(
                case_id=state.case_id,
                step_index=step_index,
                phase="observe",
                tool_calls=[
                    {"id": call.id, "name": call.name, "arguments": call.arguments}
                    for call in result.tool_calls
                ],
                observations=tool_observations,
                llm_metadata=self._step_llm_metadata(result.metadata),
                stop_reason=state.stop_reason,
                duration_ms=duration_ms,
            )

            state.messages.extend(self.llm.tool_observation_messages(observation_messages))
            if final_content:
                break

        if final_content is None:
            state.stop_reason = state.stop_reason or "max_steps"
            final_content = yield from self._finalize_from_observations_stream(state)
            streamed_final_content = streamed_final_content or final_content

        content_out = self._sanitize_user_visible_text(final_content)
        if content_out and not streamed_final_content:
            for part in self._split_stream_text(content_out):
                yield AgentStreamEvent(event="message_delta", data={"delta": part})
        yield self._react_final_event(state=state, content_out=content_out)

    def _tool_context(self, state: AgentState) -> ToolContext:
        return ToolContext(
            case_id=state.case_id,
            actor=state.actor,
            repository=self.repository,
            plugin=self._resolve_plugin(state.case_id),
            metric_repository=self.metric_repository,
        )

    def _resolve_plugin(self, case_id: str) -> DiagnosticPlugin:
        case = self.repository.get_case(case_id)
        if case is None:
            raise KeyError(case_id)
        return self.plugin_registry.require(case.equipment_type)

    def _record_route_decision(self, state: AgentState) -> None:
        self._record_agent_step(
            case_id=state.case_id,
            step_index=0,
            phase="route",
            observations=[{"route_decision": state.decision.model_dump(mode="json")}],
        )

    def _repeated_tool_call_message(self) -> str:
        return "我检测到模型在重复调用同一个工具，已停止继续执行。目前已有的分析结果如下，请根据工具轨迹和证据先进行判断。"

    def _persist_react_result(self, *, state: AgentState, content_out: str) -> AgentTurnResult:
        artifacts = self.repository.list_case_artifacts(state.case_id)
        tool_traces = self.repository.list_case_tool_traces(state.case_id)
        assistant_message = self.repository.add_message(
            AgentMessage(
                case_id=state.case_id,
                role="assistant",
                content=content_out,
                metadata=self._message_metadata(
                    decision=state.decision,
                    tool_count=len(tool_traces),
                    artifact_count=len(artifacts),
                    llm_used=True,
                    step_count=state.step_count,
                    stop_reason=state.stop_reason,
                ),
            )
        )
        self.memory.update_midterm(state.case_id, content_out[:500])
        return AgentTurnResult(message=assistant_message, artifacts=artifacts, tool_traces=tool_traces, summary=content_out)

    def _react_final_event(self, *, state: AgentState, content_out: str) -> AgentStreamEvent:
        result = self._persist_react_result(state=state, content_out=content_out)
        return AgentStreamEvent(
            event="final",
            data={
                "message": result.message.model_dump(mode="json"),
                "summary": result.summary,
                "artifacts": [artifact.model_dump(mode="json") for artifact in result.artifacts],
                "tool_traces": [trace.model_dump(mode="json") for trace in result.tool_traces],
            },
        )

    def _prepare_tool_arguments(self, tool_name: str, arguments: dict[str, Any], active_dataset_id: str | None) -> dict[str, Any]:
        prepared = dict(arguments)
        if tool_name in {"parse_dataset", "inspect_dataset", "profile_dataset", "build_trend_chart"}:
            prepared["dataset_id"] = active_dataset_id
        return prepared

    def _tool_result_observation(self, tool_name: str, tool_result) -> dict[str, Any]:
        observation = tool_result.observation
        if observation is None:
            return {
                "tool_name": tool_name,
                "summary": tool_result.summary,
                "data": tool_result.payload,
                "artifact_ids": [artifact.id for artifact in tool_result.artifacts],
                "evidence_ids": [evidence.id for evidence in tool_result.evidence],
                "next_suggestions": [],
            }
        return {
            "tool_name": observation.tool_name,
            "summary": observation.summary,
            "data": observation.data,
            "artifact_ids": observation.artifact_ids,
            "evidence_ids": observation.evidence_ids,
            "next_suggestions": observation.next_suggestions,
        }

    def _recovery_suggestions(self, tool_name: str) -> list[str]:
        if tool_name == "diagnose_performance":
            return ["profile_dataset", "build_trend_chart"]
        if tool_name in {"profile_dataset", "build_trend_chart"}:
            return ["inspect_dataset", "parse_dataset"]
        return ["inspect_dataset"]

    def _finalize_from_observations(self, state: AgentState) -> str:
        messages = list(state.messages)
        messages.append(
            {
                "role": "user",
                "content": (
                    "已经达到本轮 Agent 最大工具步数。请只基于已有 observations 生成最终中文回复。"
                    "不要输出任何 tool_calls、function call、DSML、XML、JSON 调用标记。"
                    "说明已完成哪些分析、仍缺哪些数据，以及建议下一步。"
                    f"Observations JSON: {json.dumps(state.observations, ensure_ascii=False)}"
                ),
            }
        )
        result = self._call_llm_for_summary(case_id=state.case_id, messages=messages)
        self._record_agent_step(
            case_id=state.case_id,
            step_index=state.step_count,
            phase="stop",
            observations=state.observations[-3:],
            llm_metadata=self._step_llm_metadata(result.metadata),
            stop_reason=state.stop_reason,
        )
        return result.content or "已完成本轮分析，但模型未生成最终回复。请查看工具轨迹和证据结果。"

    def _finalize_from_observations_stream(self, state: AgentState) -> Iterator[AgentStreamEvent | str]:
        messages = list(state.messages)
        messages.append(
            {
                "role": "user",
                "content": (
                    "已经达到本轮 Agent 最大工具步数。请只基于已有 observations 生成最终中文回复。"
                    "不要输出任何 tool_calls、function call、DSML、XML、JSON 调用标记。"
                    "说明已完成哪些分析、仍缺哪些数据，以及建议下一步。"
                    f"Observations JSON: {json.dumps(state.observations, ensure_ascii=False)}"
                ),
            }
        )
        result, deltas = self._call_llm_for_summary_stream(case_id=state.case_id, messages=messages)
        for delta in deltas:
            yield AgentStreamEvent(event="message_delta", data={"delta": delta})
        self._record_agent_step(
            case_id=state.case_id,
            step_index=state.step_count,
            phase="stop",
            observations=state.observations[-3:],
            llm_metadata=self._step_llm_metadata(result.metadata),
            stop_reason=state.stop_reason,
        )
        return result.content or "已完成本轮分析，但模型未生成最终回复。请查看工具轨迹和证据结果。"

    def _handle_stub_turn(
        self,
        *,
        case_id: str,
        content: str,
        active_dataset_id: str | None,
        actor: str,
        decision: RouteDecision,
    ) -> AgentTurnResult:
        if decision.intent in {"chat_response", "knowledge_qa", "clarification", "workflow_request"}:
            return self._local_reply(
                case_id=case_id,
                content=self._stub_non_tool_reply(decision=decision, has_dataset=active_dataset_id is not None),
                decision=decision,
                llm_used=False,
            )

        tool_names = self.llm.plan_tools(content, has_dataset=active_dataset_id is not None)  # type: ignore[attr-defined]
        context = ToolContext(
            case_id=case_id,
            actor=actor,
            repository=self.repository,
            plugin=self._resolve_plugin(case_id),
            metric_repository=self.metric_repository,
        )
        summaries: list[str] = []
        for name in tool_names:
            arguments: dict[str, Any] = {}
            if name in {"parse_dataset", "profile_dataset", "build_trend_chart"}:
                arguments["dataset_id"] = active_dataset_id
            result = self.registry.run(name, context, arguments)
            summaries.append(f"{name}: {result.summary}")

        artifacts = self.repository.list_case_artifacts(case_id)
        tool_traces = self.repository.list_case_tool_traces(case_id)
        if summaries:
            content_out = (
                "已完成设备性能辅助诊断。请在证据链和报告草稿基础上进行工程师确认。\n"
                + "\n".join(f"- {summary}" for summary in summaries)
            )
        else:
            content_out = "请先上传设备性能数据文件，之后我可以执行解析、画像、趋势和辅助诊断。"

        assistant_message = self.repository.add_message(
            AgentMessage(
                case_id=case_id,
                role="assistant",
                content=content_out,
                metadata=self._message_metadata(
                    decision=decision,
                    tool_count=len(tool_names),
                    artifact_count=len(artifacts),
                    llm_used=False,
                ),
            )
        )
        self.memory.update_midterm(case_id, content_out[:500])
        return AgentTurnResult(
            message=assistant_message,
            artifacts=artifacts,
            tool_traces=tool_traces,
            summary=content_out,
        )

    def _build_llm_messages(
        self,
        *,
        case_id: str,
        user_content: str,
        active_dataset_id: str | None,
        decision: RouteDecision,
    ) -> list[dict[str, Any]]:
        case = self.repository.get_case(case_id)
        datasets = self.repository.list_case_datasets(case_id)
        artifacts = self.repository.list_case_artifacts(case_id)
        evidence = self.repository.list_case_evidence(case_id)
        recent_messages = self.repository.list_case_messages(case_id)[-6:]

        context = {
            "case": case.model_dump(mode="json") if case else {},
            "active_dataset_id": active_dataset_id,
            "datasets": [
                {
                    "id": item.id,
                    "filename": item.filename,
                    "content_type": item.content_type,
                    "created_at": item.created_at.isoformat(),
                }
                for item in datasets
            ],
            "artifacts": [
                {
                    "id": item.id,
                    "kind": item.kind,
                    "title": item.title,
                    "summary": item.summary,
                    "source_file_id": item.source_file_id,
                }
                for item in artifacts[-10:]
            ],
            "evidence": [
                {
                    "id": item.id,
                    "type": item.evidence_type,
                    "title": item.title,
                    "summary": item.summary,
                    "source_artifact_id": item.source_artifact_id,
                }
                for item in evidence[-10:]
            ],
            "midterm_memory": self.memory.midterm_summaries.get(case_id),
        }
        system_prompt = (
            "你是半导体工业设备性能诊断平台的辅助诊断 Agent。"
            "你正在执行 ReAct 循环：如果还需要信息，必须通过白名单工具获取；"
            "如果已有 observations 足够回答，直接输出最终结论，不要再承诺稍后查看。"
            "不要编造没有证据支撑的根因；正式结论和处置建议需要工程师确认。"
            "不要要求访问原始文件内容；上下文只提供摘要和元数据。"
            "可以使用 Markdown 和 emoji，但默认面向工程师，直接、简洁、可执行。"
            "不要默认展示内部 case id、dataset id、artifact id，也不要要求用户手动提供 dataset id；"
            "系统会自动使用当前案例最新上传的数据。"
            "常规诊断优先调用 inspect_dataset 了解字段和样例，再调用 profile_dataset、build_trend_chart、diagnose_performance。"
        )
        history = [
            {"role": item.role, "content": item.content}
            for item in recent_messages
            if item.role in {"user", "assistant"}
        ]
        user_message = (
            f"{user_content}\n\n"
            f"Route decision JSON:\n{decision.model_dump(mode='json')}\n"
            f"Active dataset available: {bool(active_dataset_id)}\n"
            f"Case context summary JSON:\n{context}"
        )
        return [{"role": "system", "content": system_prompt}] + history + [{"role": "user", "content": user_message}]

    def _handle_non_tool_llm_turn(
        self,
        *,
        case_id: str,
        content: str,
        decision: RouteDecision,
    ) -> AgentTurnResult:
        messages = self._build_non_tool_messages(case_id=case_id, user_content=content, decision=decision)
        result = self._call_llm_for_summary(case_id=case_id, messages=messages)
        clean_content = self._sanitize_user_visible_text(result.content or "我需要更多信息才能继续。")
        return self._local_reply(
            case_id=case_id,
            content=clean_content,
            decision=decision,
            llm_used=True,
            provider=self.llm.provider_name,
            model=self.llm.model,
        )

    def _build_non_tool_messages(self, *, case_id: str, user_content: str, decision: RouteDecision) -> list[dict[str, Any]]:
        route_context = self._build_route_context(case_id=case_id)
        system_prompt = (
            "你是半导体工业设备性能诊断平台的辅助诊断 Agent。"
            "根据路由结果回复用户。可以使用 Markdown 和 emoji。"
            "不要默认展示内部 case id、dataset id、artifact id。"
            "不要要求用户手动提供 dataset id；如果需要数据，只提示用户上传数据文件。"
            "如果 response_style=brief，回复应简短。"
            "资料问答可以基于通用工程知识回答，但要说明当前尚未接入专用知识库。"
        )
        return [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"用户输入: {user_content}\n"
                    f"Route decision JSON: {decision.model_dump(mode='json')}\n"
                    f"Case state: {route_context}"
                ),
            },
        ]

    def _local_reply(
        self,
        *,
        case_id: str,
        content: str,
        decision: RouteDecision,
        llm_used: bool,
        blocked_by_state_gate: bool = False,
        provider: str | None = None,
        model: str | None = None,
    ) -> AgentTurnResult:
        clean_content = self._sanitize_user_visible_text(content)
        artifacts = self.repository.list_case_artifacts(case_id)
        tool_traces = self.repository.list_case_tool_traces(case_id)
        assistant_message = self.repository.add_message(
            AgentMessage(
                case_id=case_id,
                role="assistant",
                content=clean_content,
                metadata=self._message_metadata(
                    decision=decision,
                    tool_count=0,
                    artifact_count=len(artifacts),
                    llm_used=llm_used,
                    blocked_by_state_gate=blocked_by_state_gate,
                    provider=provider,
                    model=model,
                ),
            )
        )
        self.memory.update_midterm(case_id, clean_content[:500])
        return AgentTurnResult(message=assistant_message, artifacts=artifacts, tool_traces=tool_traces, summary=clean_content)

    def _stream_local_reply(
        self,
        *,
        case_id: str,
        content: str,
        decision: RouteDecision,
        llm_used: bool,
        blocked_by_state_gate: bool = False,
        provider: str | None = None,
        model: str | None = None,
    ) -> Iterator[AgentStreamEvent]:
        clean_content = self._sanitize_user_visible_text(content)
        for part in self._split_stream_text(clean_content):
            yield AgentStreamEvent(event="message_delta", data={"delta": part})
        artifacts = self.repository.list_case_artifacts(case_id)
        tool_traces = self.repository.list_case_tool_traces(case_id)
        assistant_message = self.repository.add_message(
            AgentMessage(
                case_id=case_id,
                role="assistant",
                content=clean_content,
                metadata=self._message_metadata(
                    decision=decision,
                    tool_count=0,
                    artifact_count=len(artifacts),
                    llm_used=llm_used,
                    blocked_by_state_gate=blocked_by_state_gate,
                    provider=provider,
                    model=model,
                ),
            )
        )
        self.memory.update_midterm(case_id, clean_content[:500])
        yield AgentStreamEvent(
            event="final",
            data={
                "message": assistant_message.model_dump(mode="json"),
                "summary": clean_content,
                "artifacts": [artifact.model_dump(mode="json") for artifact in artifacts],
                "tool_traces": [trace.model_dump(mode="json") for trace in tool_traces],
            },
        )

    def _stream_non_tool_llm_turn(
        self,
        *,
        case_id: str,
        content: str,
        decision: RouteDecision,
    ) -> Iterator[AgentStreamEvent]:
        messages = self._build_non_tool_messages(case_id=case_id, user_content=content, decision=decision)
        result, deltas = self._call_llm_for_summary_stream(case_id=case_id, messages=messages)
        clean_parts: list[str] = []
        for delta in deltas:
            clean_delta = self._sanitize_user_visible_text(delta)
            clean_parts.append(clean_delta)
            yield AgentStreamEvent(event="message_delta", data={"delta": clean_delta})
        clean_content = self._sanitize_user_visible_text(result.content or "".join(clean_parts) or "我需要更多信息才能继续。")
        artifacts = self.repository.list_case_artifacts(case_id)
        tool_traces = self.repository.list_case_tool_traces(case_id)
        assistant_message = self.repository.add_message(
            AgentMessage(
                case_id=case_id,
                role="assistant",
                content=clean_content,
                metadata=self._message_metadata(
                    decision=decision,
                    tool_count=0,
                    artifact_count=len(artifacts),
                    llm_used=True,
                    provider=self.llm.provider_name,
                    model=self.llm.model,
                ),
            )
        )
        self.memory.update_midterm(case_id, clean_content[:500])
        yield AgentStreamEvent(
            event="final",
            data={
                "message": assistant_message.model_dump(mode="json"),
                "summary": clean_content,
                "artifacts": [artifact.model_dump(mode="json") for artifact in artifacts],
                "tool_traces": [trace.model_dump(mode="json") for trace in tool_traces],
            },
        )

    def _build_route_context(self, *, case_id: str) -> CaseRouteContext:
        datasets = self.repository.list_case_datasets(case_id)
        return CaseRouteContext(
            has_dataset=bool(datasets),
            dataset_count=len(datasets),
            artifact_count=len(self.repository.list_case_artifacts(case_id)),
            evidence_count=len(self.repository.list_case_evidence(case_id)),
            latest_dataset_filename=datasets[-1].filename if datasets else None,
        )

    def _message_metadata(
        self,
        *,
        decision: RouteDecision,
        tool_count: int,
        artifact_count: int,
        llm_used: bool,
        blocked_by_state_gate: bool = False,
        provider: str | None = None,
        model: str | None = None,
        step_count: int = 0,
        stop_reason: str | None = None,
    ) -> dict[str, Any]:
        return {
            "intent": decision.intent,
            "route": decision.intent,
            "requires_dataset": decision.requires_dataset,
            "llm_used": llm_used,
            "blocked_by_state_gate": blocked_by_state_gate,
            "tool_count": tool_count,
            "artifact_count": artifact_count,
            "step_count": step_count,
            "stop_reason": stop_reason,
            "llm_provider": provider or self.llm.provider_name,
            "llm_model": model or self.llm.model,
            "llm_tool_mode": getattr(self.llm, "tool_mode", "unknown"),
        }

    def _stub_non_tool_reply(self, *, decision: RouteDecision, has_dataset: bool) -> str:
        if decision.intent == "chat_response":
            if has_dataset:
                return "你好。当前数据已就绪，可以直接告诉我你想分析的问题。"
            return "你好。请先上传设备性能 CSV，上传后我可以开始分析。"
        if decision.intent == "knowledge_qa":
            return "我可以回答设备性能诊断相关资料问题；当前专用知识库还未接入，回答会基于通用工程知识。"
        if decision.intent == "workflow_request":
            return "Workflow 能力还在规划中。当前可以先完成单次数据分析和诊断。"
        return "我需要更多信息才能继续。你可以上传数据文件，或描述想分析的问题。"

    def _sanitize_user_visible_text(self, content: str) -> str:
        sanitized = re.sub(r"<｜｜DSML｜｜tool_calls>.*?</｜｜DSML｜｜tool_calls>", "", content, flags=re.DOTALL)
        sanitized = re.sub(r"<tool_calls>.*?</tool_calls>", "", sanitized, flags=re.DOTALL | re.IGNORECASE)
        sanitized = re.sub(r"<function_call>.*?</function_call>", "", sanitized, flags=re.DOTALL | re.IGNORECASE)
        sanitized = re.sub(r"\bcase_[a-zA-Z0-9]+\b", "当前案例", sanitized)
        sanitized = re.sub(r"\bds_[a-zA-Z0-9]+\b", "当前数据集", sanitized)
        sanitized = re.sub(r"\bart_[a-zA-Z0-9]+\b", "分析结果", sanitized)
        sanitized = re.sub(r"\bmsg_[a-zA-Z0-9]+\b", "消息", sanitized)
        return sanitized

    def _split_stream_text(self, content: str) -> list[str]:
        if not content:
            return []
        parts = re.split(r"(\n|。|；|！|？)", content)
        chunks: list[str] = []
        current = ""
        for part in parts:
            current += part
            if part in {"\n", "。", "；", "！", "？"} and current:
                chunks.append(current)
                current = ""
        if current:
            chunks.append(current)
        return chunks or [content]

    def _call_llm_for_plan(
        self,
        *,
        case_id: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ):
        try:
            result = self.llm.plan_tool_calls(messages=messages, tools=tools)
        except LLMError as exc:
            self._record_llm_audit(case_id=case_id, request={"messages": messages, "tool_specs": tools}, error=str(exc))
            raise
        request_payload = result.metadata.get("request_payload")
        self._record_llm_audit(
            case_id=case_id,
            request=request_payload if isinstance(request_payload, dict) else {"messages": messages, "tools": tools},
            response=result.raw_response,
            duration_ms=int(result.metadata.get("duration_ms", 0)),
        )
        return result

    def _call_llm_for_plan_stream(
        self,
        *,
        case_id: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> tuple[Any, list[str]]:
        deltas: list[str] = []
        result = None
        try:
            for chunk in self.llm.plan_tool_calls_stream(messages=messages, tools=tools):
                if chunk.event == "delta" and chunk.delta:
                    deltas.append(chunk.delta)
                elif chunk.event == "result":
                    result = chunk.result
        except LLMError as exc:
            self._record_llm_audit(case_id=case_id, request={"messages": messages, "tool_specs": tools}, error=str(exc))
            raise
        if result is None:
            raise LLMError("LLM stream ended without a planning result", status_code=502)
        request_payload = result.metadata.get("request_payload")
        self._record_llm_audit(
            case_id=case_id,
            request=request_payload if isinstance(request_payload, dict) else {"messages": messages, "tools": tools},
            response=result.raw_response,
            duration_ms=int(result.metadata.get("duration_ms", 0)),
        )
        return result, deltas

    def _record_agent_step(
        self,
        *,
        case_id: str,
        step_index: int,
        phase: str,
        tool_calls: list[dict[str, Any]] | None = None,
        observations: list[dict[str, Any]] | None = None,
        llm_metadata: dict[str, Any] | None = None,
        stop_reason: str | None = None,
        duration_ms: int = 0,
    ) -> None:
        self.repository.add_agent_step_trace(
            AgentStepTrace(
                case_id=case_id,
                step_index=step_index,
                phase=phase,  # type: ignore[arg-type]
                tool_calls=tool_calls or [],
                observations=observations or [],
                llm_metadata=llm_metadata or {},
                stop_reason=stop_reason,
                duration_ms=duration_ms,
            )
        )

    def _step_llm_metadata(self, metadata: dict[str, Any]) -> dict[str, Any]:
        return {
            key: value
            for key, value in metadata.items()
            if key not in {"request_payload", "raw_model_content"}
        }

    def _call_llm_for_summary(self, *, case_id: str, messages: list[dict[str, Any]]):
        try:
            result = self.llm.summarize_turn(messages=messages)
        except LLMError as exc:
            self._record_llm_audit(case_id=case_id, request={"messages": messages}, error=str(exc))
            raise
        request_payload = result.metadata.get("request_payload")
        self._record_llm_audit(
            case_id=case_id,
            request=request_payload if isinstance(request_payload, dict) else {"messages": messages},
            response=result.raw_response,
            duration_ms=int(result.metadata.get("duration_ms", 0)),
        )
        return result

    def _call_llm_for_summary_stream(self, *, case_id: str, messages: list[dict[str, Any]]) -> tuple[Any, list[str]]:
        deltas: list[str] = []
        result = None
        try:
            for chunk in self.llm.summarize_turn_stream(messages=messages):
                if chunk.event == "delta" and chunk.delta:
                    deltas.append(chunk.delta)
                elif chunk.event == "result":
                    result = chunk.result
        except LLMError as exc:
            self._record_llm_audit(case_id=case_id, request={"messages": messages}, error=str(exc))
            raise
        if result is None:
            raise LLMError("LLM stream ended without a summary result", status_code=502)
        request_payload = result.metadata.get("request_payload")
        self._record_llm_audit(
            case_id=case_id,
            request=request_payload if isinstance(request_payload, dict) else {"messages": messages},
            response=result.raw_response,
            duration_ms=int(result.metadata.get("duration_ms", 0)),
        )
        return result, deltas

    def _record_llm_audit(
        self,
        *,
        case_id: str,
        request: dict[str, Any],
        response: dict[str, Any] | None = None,
        error: str | None = None,
        duration_ms: int = 0,
    ) -> None:
        self.repository.add_llm_audit_event(
            LLMAuditEvent(
                case_id=case_id,
                provider=self.llm.provider_name,
                model=self.llm.model,
                request=request,
                response=response,
                error=error,
                duration_ms=duration_ms,
            )
        )
