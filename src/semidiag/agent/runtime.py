from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from semidiag.agent.llm import LLMError, LLMProvider, StubLLMProvider
from semidiag.agent.memory import MemoryService
from semidiag.domain import AgentMessage, AnalysisArtifact, LLMAuditEvent, ToolCallTrace
from semidiag.infrastructure.repository import SQLiteRepository
from semidiag.plugins import GenericEquipmentPlugin
from semidiag.tools import ToolContext, ToolRegistry, build_default_registry


@dataclass
class AgentTurnResult:
    message: AgentMessage
    artifacts: list[AnalysisArtifact]
    tool_traces: list[ToolCallTrace]
    summary: str


class AgentRuntime:
    def __init__(
        self,
        repository: SQLiteRepository,
        registry: ToolRegistry | None = None,
        llm: LLMProvider | None = None,
        memory: MemoryService | None = None,
    ) -> None:
        self.repository = repository
        self.registry = registry or build_default_registry()
        self.llm = llm or StubLLMProvider()
        self.memory = memory or MemoryService()
        self.plugin = GenericEquipmentPlugin()

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
        if isinstance(self.llm, StubLLMProvider):
            return self._handle_stub_turn(
                case_id=case_id,
                content=content,
                active_dataset_id=active_dataset_id,
                actor=actor,
            )

        context = ToolContext(
            case_id=case_id,
            actor=actor,
            repository=self.repository,
            plugin=self.plugin,
        )
        messages = self._build_llm_messages(case_id=case_id, user_content=content, active_dataset_id=active_dataset_id)
        tools = self.registry.openai_tools()
        plan_result = self._call_llm_for_plan(case_id=case_id, messages=messages, tools=tools)
        if not plan_result.tool_calls:
            raise LLMError("LLM did not return any tool calls for this diagnostic request", status_code=502)

        tool_messages: list[dict[str, Any]] = []
        for call in plan_result.tool_calls:
            if self.registry.get_tool(call.name) is None:
                raise LLMError(f"LLM requested unknown tool: {call.name}", status_code=502)
            arguments = dict(call.arguments)
            if call.name in {"parse_dataset", "profile_dataset", "build_trend_chart"}:
                arguments["dataset_id"] = active_dataset_id
            result = self.registry.run(call.name, context, arguments)
            tool_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "name": call.name,
                    "content": result.summary,
                }
            )

        assistant_tool_message = {
            "role": "assistant",
            "content": plan_result.content or "",
            "tool_calls": [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {"name": call.name, "arguments": json.dumps(call.arguments, ensure_ascii=False)},
                }
                for call in plan_result.tool_calls
            ],
        }
        summarize_messages = messages + [assistant_tool_message] + tool_messages
        final_result = self._call_llm_for_summary(case_id=case_id, messages=summarize_messages)
        content_out = final_result.content or "已完成工具调用，但模型没有生成最终回答。"

        artifacts = self.repository.list_case_artifacts(case_id)
        tool_traces = self.repository.list_case_tool_traces(case_id)

        assistant_message = self.repository.add_message(
            AgentMessage(
                case_id=case_id,
                role="assistant",
                content=content_out,
                metadata={
                    "tool_count": len(plan_result.tool_calls),
                    "artifact_count": len(artifacts),
                    "llm_provider": self.llm.provider_name,
                    "llm_model": self.llm.model,
                },
            )
        )
        self.memory.update_midterm(case_id, content_out[:500])
        return AgentTurnResult(
            message=assistant_message,
            artifacts=artifacts,
            tool_traces=tool_traces,
            summary=content_out,
        )

    def _handle_stub_turn(
        self,
        *,
        case_id: str,
        content: str,
        active_dataset_id: str | None,
        actor: str,
    ) -> AgentTurnResult:
        tool_names = self.llm.plan_tools(content, has_dataset=active_dataset_id is not None)  # type: ignore[attr-defined]
        context = ToolContext(
            case_id=case_id,
            actor=actor,
            repository=self.repository,
            plugin=self.plugin,
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
                metadata={"tool_count": len(tool_names), "artifact_count": len(artifacts), "llm_provider": "stub"},
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
            "你必须通过白名单工具分析数据，并基于 Artifact 和 Evidence 输出结论。"
            "不要编造没有证据支撑的根因；正式结论和处置建议需要工程师确认。"
            "不要要求访问原始文件内容；上下文只提供摘要和元数据。"
        )
        history = [
            {"role": item.role, "content": item.content}
            for item in recent_messages
            if item.role in {"user", "assistant"}
        ]
        user_message = (
            f"{user_content}\n\n"
            f"Active dataset id: {active_dataset_id or 'none'}\n"
            f"Case context summary JSON:\n{context}"
        )
        return [{"role": "system", "content": system_prompt}] + history + [{"role": "user", "content": user_message}]

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
            self._record_llm_audit(case_id=case_id, request={"messages": messages, "tools": tools}, error=str(exc))
            raise
        self._record_llm_audit(
            case_id=case_id,
            request={"messages": messages, "tools": tools},
            response=result.raw_response,
            duration_ms=int(result.metadata.get("duration_ms", 0)),
        )
        return result

    def _call_llm_for_summary(self, *, case_id: str, messages: list[dict[str, Any]]):
        try:
            result = self.llm.summarize_turn(messages=messages)
        except LLMError as exc:
            self._record_llm_audit(case_id=case_id, request={"messages": messages}, error=str(exc))
            raise
        self._record_llm_audit(
            case_id=case_id,
            request={"messages": messages},
            response=result.raw_response,
            duration_ms=int(result.metadata.get("duration_ms", 0)),
        )
        return result

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
