from __future__ import annotations

import json
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Protocol

import httpx
from pydantic import BaseModel, Field

from semidiag.config import LLMConfig


class LLMError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


class LLMToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class LLMResult(BaseModel):
    content: str = ""
    tool_calls: list[LLMToolCall] = Field(default_factory=list)
    raw_response: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LLMProvider(Protocol):
    provider_name: str
    model: str

    def plan_tool_calls(self, *, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> LLMResult:
        raise NotImplementedError

    def summarize_turn(self, *, messages: list[dict[str, Any]]) -> LLMResult:
        raise NotImplementedError


class StubLLMProvider:
    """Deterministic provider used to validate orchestration without a real LLM."""

    provider_name = "stub"
    model = "deterministic-stub"

    def plan_tools(self, message: str, has_dataset: bool) -> list[str]:
        normalized = message.lower()
        if not has_dataset:
            return []
        if any(word in normalized for word in ["report", "报告"]):
            return ["parse_dataset", "profile_dataset", "build_trend_chart", "diagnose_performance", "generate_report"]
        if any(word in normalized for word in ["diagnose", "诊断", "异常", "建议", "analyze", "分析"]):
            return ["parse_dataset", "profile_dataset", "build_trend_chart", "diagnose_performance"]
        return ["parse_dataset", "profile_dataset"]

    def plan_tool_calls(self, *, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> LLMResult:
        user_message = next((item.get("content", "") for item in reversed(messages) if item.get("role") == "user"), "")
        has_dataset = "active dataset id:" in user_message.lower()
        calls = [
            LLMToolCall(id=f"stub_{index}", name=name, arguments={})
            for index, name in enumerate(self.plan_tools(user_message, has_dataset), start=1)
        ]
        return LLMResult(content="", tool_calls=calls, metadata={"provider": self.provider_name, "model": self.model})

    def summarize_turn(self, *, messages: list[dict[str, Any]]) -> LLMResult:
        tool_messages = [item.get("content", "") for item in messages if item.get("role") == "tool"]
        content = (
            "已完成设备性能辅助诊断。请在证据链和报告草稿基础上进行工程师确认。\n"
            + "\n".join(f"- {summary}" for summary in tool_messages)
        )
        return LLMResult(content=content, metadata={"provider": self.provider_name, "model": self.model})


@dataclass
class OpenAICompatibleProvider:
    config: LLMConfig
    client: httpx.Client = field(init=False)

    def __post_init__(self) -> None:
        self.client = httpx.Client(timeout=self.config.timeout, trust_env=False)

    @property
    def provider_name(self) -> str:
        return "openai_compatible"

    @property
    def model(self) -> str:
        return self.config.model

    def plan_tool_calls(self, *, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> LLMResult:
        return self._chat(messages=messages, tools=tools, tool_choice="auto")

    def summarize_turn(self, *, messages: list[dict[str, Any]]) -> LLMResult:
        return self._chat(messages=messages, tools=None, tool_choice=None)

    def _chat(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        tool_choice: str | None,
    ) -> LLMResult:
        url = self.config.base_url.rstrip("/") + "/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
        }
        if tools is not None:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice or "auto"

        started = perf_counter()
        try:
            response = self.client.post(url, headers=headers, json=payload)
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise LLMError(f"LLM request timed out after {self.config.timeout}s", status_code=504) from exc
        except httpx.HTTPStatusError as exc:
            raise LLMError(f"LLM HTTP error {exc.response.status_code}: {exc.response.text}", status_code=502) from exc
        except httpx.HTTPError as exc:
            raise LLMError(f"LLM request failed: {exc}", status_code=502) from exc

        raw = response.json()
        try:
            message = raw["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("LLM response does not contain choices[0].message", status_code=502) from exc

        tool_calls: list[LLMToolCall] = []
        for item in message.get("tool_calls") or []:
            function = item.get("function") or {}
            raw_arguments = function.get("arguments") or "{}"
            try:
                arguments = json.loads(raw_arguments) if isinstance(raw_arguments, str) else raw_arguments
            except json.JSONDecodeError as exc:
                raise LLMError(f"LLM returned invalid tool arguments for {function.get('name')}", status_code=502) from exc
            if not isinstance(arguments, dict):
                raise LLMError(f"LLM tool arguments must be an object for {function.get('name')}", status_code=502)
            tool_calls.append(
                LLMToolCall(
                    id=item.get("id") or f"call_{len(tool_calls) + 1}",
                    name=function.get("name") or "",
                    arguments=arguments,
                )
            )

        duration_ms = int((perf_counter() - started) * 1000)
        return LLMResult(
            content=message.get("content") or "",
            tool_calls=tool_calls,
            raw_response=raw,
            metadata={"provider": self.provider_name, "model": self.model, "duration_ms": duration_ms},
        )


def build_llm_provider(config: LLMConfig) -> LLMProvider:
    if config.provider == "openai_compatible":
        return OpenAICompatibleProvider(config)
    return StubLLMProvider()


def redact_llm_request(request: dict[str, Any]) -> dict[str, Any]:
    redacted = json.loads(json.dumps(request, ensure_ascii=False))
    headers = redacted.get("headers")
    if isinstance(headers, dict) and "Authorization" in headers:
        headers["Authorization"] = "Bearer ***"
    if "api_key" in redacted:
        redacted["api_key"] = "***"
    return redacted
