from __future__ import annotations

import json
import re
from collections.abc import Iterator
from typing import Any

from semidiag.agent.llm import LLMResult, LLMStreamChunk, LLMToolCall
from semidiag.tools import ToolRegistry


def build_csv_tool_registry() -> ToolRegistry:
    from semidiag.extensions import ExtensionLoader
    from semidiag.plugins import CalibrationPluginRegistry, ToolScopeBuilder

    calibration_registry = CalibrationPluginRegistry()
    ExtensionLoader("business").load_plugins(calibration_registry)
    return ToolScopeBuilder(common_registry=ToolRegistry(), calibration_registry=calibration_registry).build(
        selected_plugin_ids=["csv.file_analysis"]
    )


class DeterministicLLMProvider:
    provider_name = "test_fake"
    model = "deterministic-test-fake"
    tool_mode = "native"

    def __init__(self) -> None:
        self.plan_round = 0

    def tool_specs(self, registry: Any) -> list[dict[str, Any]]:
        return registry.openai_tools()

    def summarize_turn(self, *, messages: list[dict[str, Any]]) -> LLMResult:
        first_content = messages[0].get("content", "") if messages else ""
        if "路由器" in first_content:
            return LLMResult(content=json.dumps(self._route(messages), ensure_ascii=False), metadata=self._metadata())
        if "插件选择器" in first_content:
            user_payload = messages[-1].get("content", "") if messages else ""
            user_line = next((line for line in user_payload.splitlines() if line.startswith("User content:")), "")
            if "lt.example.offline_check" in user_payload and "offline" in user_line.lower():
                plugin_ids = ["lt.example.offline_check"]
            elif "csv.file_analysis" in user_payload:
                plugin_ids = ["csv.file_analysis"]
            else:
                plugin_ids = []
            return LLMResult(
                content=json.dumps({"plugin_ids": plugin_ids, "reason": "Matched by test fake.", "confidence": 0.9}),
                metadata=self._metadata(),
            )
        content = "你好。请上传设备性能数据文件，上传后我可以开始分析。" if self._is_greeting(messages) else self._final_answer(messages)
        return LLMResult(content=content, metadata=self._metadata())

    def summarize_turn_stream(self, *, messages: list[dict[str, Any]]) -> Iterator[LLMStreamChunk]:
        result = self.summarize_turn(messages=messages)
        for part in self._split_stream_text(result.content):
            yield LLMStreamChunk(event="delta", delta=part)
        yield LLMStreamChunk(event="result", result=result)

    def plan_tool_calls(self, *, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> LLMResult:
        if any(item.get("role") == "tool" for item in messages):
            return LLMResult(content=self._final_answer(messages), metadata=self._metadata())
        self.plan_round += 1
        tool_names = self._tool_names(tools)
        requested = self._requested_tool_names(messages)
        calls = [
            LLMToolCall(id=f"fake_{index}", name=name, arguments={})
            for index, name in enumerate(requested, start=1)
            if name in tool_names
        ]
        return LLMResult(tool_calls=calls, metadata=self._metadata())

    def plan_tool_calls_stream(self, *, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Iterator[LLMStreamChunk]:
        result = self.plan_tool_calls(messages=messages, tools=tools)
        if result.content:
            for part in self._split_stream_text(result.content):
                yield LLMStreamChunk(event="delta", delta=part)
        yield LLMStreamChunk(event="result", result=result)

    def assistant_plan_message(self, result: LLMResult) -> dict[str, Any]:
        return {
            "role": "assistant",
            "content": result.content or "",
            "tool_calls": [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {"name": call.name, "arguments": json.dumps(call.arguments, ensure_ascii=False)},
                }
                for call in result.tool_calls
            ],
        }

    def tool_observation_messages(self, observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "role": "tool",
                "tool_call_id": item["tool_call_id"],
                "name": item["tool_name"],
                "content": json.dumps(item["observation"], ensure_ascii=False),
            }
            for item in observations
        ]

    def _route(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        content = messages[-1].get("content", "") if messages else ""
        normalized = content.lower()
        if any(token in normalized for token in ["报告", "report"]):
            intent = "report_generation"
            goal = "生成诊断报告"
        elif any(token in normalized for token in ["诊断", "异常", "建议", "故障", "diagnose"]):
            intent = "diagnosis"
            goal = "诊断设备性能异常"
        elif any(token in normalized for token in ["分析", "趋势", "画像", "比较", "analyze"]):
            intent = "data_analysis"
            goal = "分析设备性能数据"
        elif any(token in normalized for token in ["资料", "手册", "原理", "是什么", "什么意思"]):
            intent = "knowledge_qa"
            goal = "资料问答"
        else:
            intent = "chat_response"
            goal = "用户问候"
        return {
            "intent": intent,
            "requires_dataset": intent in {"data_analysis", "diagnosis", "report_generation"},
            "requires_knowledge": intent == "knowledge_qa",
            "target_workflow": None,
            "user_goal": goal,
            "response_style": "brief" if intent == "chat_response" else "normal",
            "reason": "Deterministic test route.",
        }

    def _requested_tool_names(self, messages: list[dict[str, Any]]) -> list[str]:
        content = "\n".join(str(item.get("content", "")) for item in messages)
        normalized = content.lower()
        if "报告" in normalized or "report_generation" in normalized:
            return ["parse_dataset", "profile_dataset", "build_trend_chart", "diagnose_performance", "generate_report"]
        if "趋势" in normalized or "data_analysis" in normalized:
            return ["parse_dataset", "profile_dataset", "build_trend_chart"]
        return ["parse_dataset", "profile_dataset", "build_trend_chart", "diagnose_performance"]

    def _tool_names(self, tools: list[dict[str, Any]]) -> set[str]:
        return {tool.get("function", {}).get("name", "") for tool in tools}

    def _final_answer(self, messages: list[dict[str, Any]]) -> str:
        tool_messages = [item.get("content", "") for item in messages if item.get("role") == "tool"]
        if not tool_messages:
            return "已完成设备性能辅助诊断。请在证据链和报告草稿基础上进行工程师确认。"
        return (
            "已完成设备性能辅助诊断。请在证据链和报告草稿基础上进行工程师确认。\n"
            + "\n".join(f"- {summary}" for summary in tool_messages)
        )

    def _is_greeting(self, messages: list[dict[str, Any]]) -> bool:
        content = messages[-1].get("content", "").strip().lower() if messages else ""
        return any(token in content for token in ["你好", "您好", "hello", "hi"])

    def _split_stream_text(self, content: str) -> list[str]:
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

    def _metadata(self) -> dict[str, str]:
        return {"provider": self.provider_name, "model": self.model, "tool_mode": self.tool_mode}
