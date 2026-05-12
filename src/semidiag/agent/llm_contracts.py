from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field


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


@dataclass
class LLMStreamChunk:
    event: Literal["delta", "result"]
    delta: str = ""
    result: LLMResult | None = None


class LLMProvider(Protocol):
    provider_name: str
    model: str
    tool_mode: str

    def tool_specs(self, registry: Any) -> list[dict[str, Any]]:
        raise NotImplementedError

    def plan_tool_calls(self, *, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> LLMResult:
        raise NotImplementedError

    def plan_tool_calls_stream(self, *, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Iterator[LLMStreamChunk]:
        raise NotImplementedError

    def summarize_turn(self, *, messages: list[dict[str, Any]]) -> LLMResult:
        raise NotImplementedError

    def summarize_turn_stream(self, *, messages: list[dict[str, Any]]) -> Iterator[LLMStreamChunk]:
        raise NotImplementedError

    def assistant_plan_message(self, result: LLMResult) -> dict[str, Any]:
        raise NotImplementedError

    def tool_observation_messages(self, observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        raise NotImplementedError
