from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from uuid import uuid4

from pydantic_ai.messages import ModelRequest, ModelResponse, RetryPromptPart, TextPart, ToolCallPart, ToolReturnPart, UserPromptPart
from pydantic_ai.models.function import DeltaToolCall, FunctionModel
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

from pr_agents.models import AgentEntry, IntentMode, SourcePattern
from pr_agents.settings import Settings


def _detect_business_code(user_message: str) -> str:
    upper = user_message.upper()
    if "B001" in upper:
        return "B001"
    return "A_DEMO"


def _detect_entry(user_message: str) -> str:
    lower = user_message.lower()
    if "database" in lower or "数据库" in user_message:
        return AgentEntry.DATABASE.value
    return AgentEntry.FILE.value


def _detect_source_pattern(business_code: str) -> str:
    if business_code == "B001":
        return SourcePattern.SHARED_FILE.value
    return SourcePattern.PER_BUSINESS_FILE.value


def _is_report_request(content: str) -> bool:
    lower = content.lower()
    return (
        "show me the report again" in lower
        or "show the report again" in lower
        or "report again" in lower
        or "show latest report" in lower
        or "再看报告" in content
        or "重新看报告" in content
    )


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


def _is_cancel_request(content: str) -> bool:
    lower = content.lower()
    return "cancel" in lower or "取消" in content or "停止任务" in content


def _looks_like_analysis_request(content: str) -> bool:
    lower = content.lower()
    markers = (
        "a_demo",
        "b001",
        "database",
        "scientific plot",
        "report",
        "analy",
        "chart",
        "plot",
        "分析",
        "报告",
        "画图",
        "绘图",
        "数据库",
    )
    return any(marker in lower or marker in content for marker in markers)


def _chat_reply(content: str) -> str:
    normalized = content.strip().lower()
    if normalized in {"hi", "hello", "hey", "你好", "您好", "嗨", "在吗"}:
        return (
            "你好。我可以帮你分析 demo 数据、生成科学绘图和报告。"
            "你可以直接说：请用 A_DEMO 文件数据生成科学绘图和报告。"
        )
    if "你是谁" in content or "你能做什么" in content or "怎么用" in content or normalized == "help":
        return (
            "我是一个任务型分析 Agent。你可以让我跑文件分析、数据库分析、查看报告，"
            "或者概括报告重点。"
        )
    return "我可以直接回复，也可以调用分析工作流。你可以试试文件 demo、数据库 demo，或者让我概括最近的报告。"


async def _yield_text(content: str, chunk_size: int = 12) -> AsyncIterator[str]:
    text = content or ""
    for index in range(0, len(text), chunk_size):
        await asyncio.sleep(0.15)
        yield text[index : index + chunk_size]


@dataclass
class FakeLLM:
    name: str = IntentMode.FAKE.value

    def build_model(self) -> FunctionModel:
        return FunctionModel(function=self._function, stream_function=self._stream_function, model_name=self.name)

    async def _function(self, messages, _agent_info) -> ModelResponse:
        decision = self._decide(messages)
        if decision["kind"] == "tool":
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name=decision["tool_name"],
                        args=json.dumps(decision["tool_args"], ensure_ascii=False),
                        tool_call_id=decision["tool_call_id"],
                    )
                ]
            )
        return ModelResponse(parts=[TextPart(content=decision["text"])])

    async def _stream_function(self, messages, _agent_info) -> AsyncIterator[str | dict[int, DeltaToolCall]]:
        decision = self._decide(messages)
        if decision["kind"] == "tool":
            yield {
                0: DeltaToolCall(
                    name=decision["tool_name"],
                    json_args=json.dumps(decision["tool_args"], ensure_ascii=False),
                    tool_call_id=decision["tool_call_id"],
                )
            }
            return
        async for chunk in _yield_text(decision["text"]):
            yield chunk

    def _decide(self, messages) -> dict[str, object]:
        last_message = messages[-1] if messages else None
        if not isinstance(last_message, ModelRequest):
            return {
                "kind": "text",
                "text": "I can help with file analysis, database analysis, and report follow-up.",
            }

        tool_return = next((part for part in last_message.parts if isinstance(part, ToolReturnPart)), None)
        if tool_return is not None:
            content = tool_return.content if isinstance(tool_return.content, str) else str(tool_return.content)
            return {"kind": "text", "text": content}

        retry_prompt = next((part for part in last_message.parts if isinstance(part, RetryPromptPart)), None)
        if retry_prompt is not None:
            retry_tool_name = retry_prompt.tool_name or ""
            if retry_tool_name in {"run_db_analysis_workflow", "analyze_source"}:
                user_prompt = self._latest_user_prompt(messages)
                return {
                    "kind": "tool",
                    "tool_name": retry_tool_name,
                    "tool_args": {
                        "objective": user_prompt,
                    },
                    "tool_call_id": f"call-{uuid4().hex[:8]}",
                }
            if retry_tool_name == "run_file_analysis_workflow":
                user_prompt = self._latest_user_prompt(messages)
                business_code = _detect_business_code(user_prompt)
                return {
                    "kind": "tool",
                    "tool_name": "run_file_analysis_workflow",
                    "tool_args": {
                        "business_code": business_code,
                        "objective": user_prompt,
                        "chart_type": "scientific_plot",
                        "source_pattern": _detect_source_pattern(business_code),
                    },
                    "tool_call_id": f"call-{uuid4().hex[:8]}",
                }

        user_prompt = self._latest_user_prompt(messages)
        business_code = _detect_business_code(user_prompt)
        entry = _detect_entry(user_prompt)

        if _is_report_summary_request(user_prompt):
            return {
                "kind": "tool",
                "tool_name": "summarize_report",
                "tool_args": {},
                "tool_call_id": f"call-{uuid4().hex[:8]}",
            }
        if _is_cancel_request(user_prompt):
            return {
                "kind": "tool",
                "tool_name": "cancel_task",
                "tool_args": {},
                "tool_call_id": f"call-{uuid4().hex[:8]}",
            }
        if _is_report_request(user_prompt):
            return {
                "kind": "tool",
                "tool_name": "load_latest_report",
                "tool_args": {},
                "tool_call_id": f"call-{uuid4().hex[:8]}",
            }
        if _looks_like_analysis_request(user_prompt):
            return {
                "kind": "tool",
                "tool_name": "analyze_source",
                "tool_args": {"objective": user_prompt},
                "tool_call_id": f"call-{uuid4().hex[:8]}",
            }
        return {"kind": "text", "text": _chat_reply(user_prompt)}

    @staticmethod
    def _latest_user_prompt(messages) -> str:
        for message in reversed(messages):
            if not isinstance(message, ModelRequest):
                continue
            prompt = next((part.content for part in message.parts if isinstance(part, UserPromptPart)), None)
            if isinstance(prompt, str) and prompt:
                return prompt
        return ""


@dataclass
class GLMProvider:
    base_url: str | None
    api_key: str | None

    def is_configured(self) -> bool:
        return bool((self.base_url or "").strip() and (self.api_key or "").strip())

    def build_model(self, model_name: str) -> OpenAIModel:
        return OpenAIModel(
            model_name,
            provider=OpenAIProvider(base_url=(self.base_url or "").rstrip("/"), api_key=self.api_key or ""),
        )


def build_agent_models(settings: Settings):
    fake = FakeLLM()
    if settings.intent_mode == IntentMode.LLM:
        provider = GLMProvider(base_url=settings.llm_base_url, api_key=settings.llm_api_key)
        if provider.is_configured():
            return provider.build_model(settings.llm_model), fake.build_model(), IntentMode.LLM.value
    return fake.build_model(), None, IntentMode.FAKE.value


def build_agent_model(settings: Settings):
    model, _fallback_model, mode = build_agent_models(settings)
    return model, mode
