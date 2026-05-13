from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any

import httpx

from semidiag.agent.llm_audit import redact_llm_request
from semidiag.agent.llm_contracts import LLMError, LLMProvider, LLMResult, LLMStreamChunk, LLMToolCall
from semidiag.agent.llm_prompt_xml import PromptXmlJsonParser
from semidiag.config import LLMConfig

__all__ = [
    "LLMError",
    "LLMProvider",
    "LLMResult",
    "LLMStreamChunk",
    "LLMToolCall",
    "OpenAINativeToolProvider",
    "OpenAIPromptXmlJsonProvider",
    "PromptXmlJsonParser",
    "build_llm_provider",
    "redact_llm_request",
]


@dataclass
class OpenAIChatClient:
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

    @property
    def tool_mode(self) -> str:
        return self.config.tool_mode

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
        metadata: dict[str, Any] = {
            "provider": self.provider_name,
            "model": self.model,
            "tool_mode": self.tool_mode,
            "duration_ms": duration_ms,
            "request_payload": payload,
        }
        if "reasoning_content" in message:
            metadata["reasoning_content"] = message.get("reasoning_content") or ""
        return LLMResult(
            content=message.get("content") or "",
            tool_calls=tool_calls,
            raw_response=raw,
            metadata=metadata,
        )

    def _chat_stream(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        tool_choice: str | None,
    ) -> Iterator[LLMStreamChunk]:
        url = self.config.base_url.rstrip("/") + "/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "stream": True,
        }
        if tools is not None:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice or "auto"

        started = perf_counter()
        content_parts: list[str] = []
        tool_parts: dict[int, dict[str, Any]] = {}
        raw_chunks: list[dict[str, Any]] = []
        finish_reason: str | None = None
        reasoning_parts: list[str] = []

        try:
            with self.client.stream("POST", url, headers=headers, json=payload) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    if line.startswith("data:"):
                        line = line.removeprefix("data:").strip()
                    if line == "[DONE]":
                        break
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise LLMError("LLM stream returned invalid JSON chunk", status_code=502) from exc
                    raw_chunks.append(chunk)
                    choice = (chunk.get("choices") or [{}])[0]
                    finish_reason = choice.get("finish_reason") or finish_reason
                    delta = choice.get("delta") or {}
                    if delta.get("reasoning_content"):
                        reasoning_parts.append(str(delta.get("reasoning_content")))
                    text_delta = delta.get("content")
                    if text_delta:
                        text = str(text_delta)
                        content_parts.append(text)
                        yield LLMStreamChunk(event="delta", delta=text)
                    for item in delta.get("tool_calls") or []:
                        index = int(item.get("index", len(tool_parts)))
                        existing = tool_parts.setdefault(index, {"id": "", "name": "", "arguments": ""})
                        if item.get("id"):
                            existing["id"] += str(item["id"])
                        function = item.get("function") or {}
                        if function.get("name"):
                            existing["name"] += str(function["name"])
                        if function.get("arguments"):
                            existing["arguments"] += str(function["arguments"])
        except httpx.TimeoutException as exc:
            raise LLMError(f"LLM stream timed out after {self.config.timeout}s", status_code=504) from exc
        except httpx.HTTPStatusError as exc:
            raise LLMError(f"LLM HTTP error {exc.response.status_code}: {exc.response.text}", status_code=502) from exc
        except httpx.HTTPError as exc:
            raise LLMError(f"LLM stream failed: {exc}", status_code=502) from exc

        tool_calls: list[LLMToolCall] = []
        for index in sorted(tool_parts):
            item = tool_parts[index]
            raw_arguments = item.get("arguments") or "{}"
            try:
                arguments = json.loads(raw_arguments)
            except json.JSONDecodeError as exc:
                raise LLMError(f"LLM returned invalid streaming tool arguments for {item.get('name')}", status_code=502) from exc
            if not isinstance(arguments, dict):
                raise LLMError(f"LLM streaming tool arguments must be an object for {item.get('name')}", status_code=502)
            tool_calls.append(
                LLMToolCall(
                    id=item.get("id") or f"call_{index + 1}",
                    name=item.get("name") or "",
                    arguments=arguments,
                )
            )

        duration_ms = int((perf_counter() - started) * 1000)
        metadata: dict[str, Any] = {
            "provider": self.provider_name,
            "model": self.model,
            "tool_mode": self.tool_mode,
            "duration_ms": duration_ms,
            "finish_reason": finish_reason,
            "request_payload": payload,
        }
        if reasoning_parts:
            metadata["reasoning_content"] = "".join(reasoning_parts)
        yield LLMStreamChunk(
            event="result",
            result=LLMResult(
                content="".join(content_parts),
                tool_calls=tool_calls,
                raw_response={"stream": True, "chunks": raw_chunks},
                metadata=metadata,
            ),
        )


@dataclass
class OpenAINativeToolProvider:
    config: LLMConfig
    chat: OpenAIChatClient = field(init=False)

    def __post_init__(self) -> None:
        self.chat = OpenAIChatClient(self.config)

    @property
    def client(self) -> httpx.Client:
        return self.chat.client

    @client.setter
    def client(self, value: httpx.Client) -> None:
        self.chat.client = value

    @property
    def provider_name(self) -> str:
        return "openai_compatible"

    @property
    def model(self) -> str:
        return self.config.model

    @property
    def tool_mode(self) -> str:
        return "native"

    def plan_tool_calls(self, *, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> LLMResult:
        return self.chat._chat(messages=messages, tools=tools, tool_choice="auto")

    def plan_tool_calls_stream(self, *, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Iterator[LLMStreamChunk]:
        yield from self.chat._chat_stream(messages=messages, tools=tools, tool_choice="auto")

    def tool_specs(self, registry: Any) -> list[dict[str, Any]]:
        return registry.openai_tools()

    def summarize_turn(self, *, messages: list[dict[str, Any]]) -> LLMResult:
        return self.chat._chat(messages=messages, tools=None, tool_choice=None)

    def summarize_turn_stream(self, *, messages: list[dict[str, Any]]) -> Iterator[LLMStreamChunk]:
        yield from self.chat._chat_stream(messages=messages, tools=None, tool_choice=None)

    def assistant_plan_message(self, result: LLMResult) -> dict[str, Any]:
        message = {
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
        if "reasoning_content" in result.metadata:
            message["reasoning_content"] = result.metadata["reasoning_content"]
        return message

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


@dataclass
class OpenAIPromptXmlJsonProvider:
    config: LLMConfig
    chat: OpenAIChatClient = field(init=False)

    def __post_init__(self) -> None:
        self.chat = OpenAIChatClient(self.config)

    @property
    def client(self) -> httpx.Client:
        return self.chat.client

    @client.setter
    def client(self, value: httpx.Client) -> None:
        self.chat.client = value

    @property
    def provider_name(self) -> str:
        return "openai_compatible"

    @property
    def model(self) -> str:
        return self.config.model

    @property
    def tool_mode(self) -> str:
        return "prompt_xml_json"

    def plan_tool_calls(self, *, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> LLMResult:
        prompt_messages = self._build_prompt_messages(messages=messages, tools=tools)
        result = self.chat._chat(messages=prompt_messages, tools=None, tool_choice=None)
        try:
            parsed = PromptXmlJsonParser.parse(result.content)
        except LLMError as first_error:
            repair_messages = prompt_messages + [
                {"role": "assistant", "content": result.content or ""},
                {
                    "role": "user",
                    "content": (
                        "上一条回复不符合 XML+JSON 工具协议。请重新输出，且只输出一个 XML 块："
                        "<tool_calls>JSON数组</tool_calls> 或 <final_answer>最终回复</final_answer>。"
                        "不要输出任何解释、Markdown 代码块或前置文本。"
                    ),
                },
            ]
            result = self.chat._chat(messages=repair_messages, tools=None, tool_choice=None)
            result.metadata["repair_reason"] = str(first_error)
            parsed = PromptXmlJsonParser.parse(result.content)
        result.metadata["tool_mode"] = self.tool_mode
        result.metadata["raw_model_content"] = result.content
        if parsed["action"] == "final_answer":
            result.content = parsed["content"]
            result.tool_calls = []
            return result
        result.content = ""
        result.tool_calls = parsed["tool_calls"]
        return result

    def plan_tool_calls_stream(self, *, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> Iterator[LLMStreamChunk]:
        prompt_messages = self._build_prompt_messages(messages=messages, tools=tools)
        stream_result: LLMResult | None = None
        for chunk in self.chat._chat_stream(messages=prompt_messages, tools=None, tool_choice=None):
            if chunk.event == "result":
                stream_result = chunk.result
        if stream_result is None:
            raise LLMError("LLM stream ended without a result", status_code=502)
        try:
            parsed = PromptXmlJsonParser.parse(stream_result.content)
        except LLMError as first_error:
            repair_messages = prompt_messages + [
                {"role": "assistant", "content": stream_result.content or ""},
                {
                    "role": "user",
                    "content": (
                        "上一条回复不符合 XML+JSON 工具协议。请重新输出，且只输出一个 XML 块："
                        "<tool_calls>JSON数组</tool_calls> 或 <final_answer>最终回复</final_answer>。"
                        "不要输出任何解释、Markdown 代码块或前置文本。"
                    ),
                },
            ]
            stream_result = self.chat._chat(messages=repair_messages, tools=None, tool_choice=None)
            stream_result.metadata["repair_reason"] = str(first_error)
            parsed = PromptXmlJsonParser.parse(stream_result.content)
        stream_result.metadata["tool_mode"] = self.tool_mode
        stream_result.metadata["raw_model_content"] = stream_result.content
        if parsed["action"] == "final_answer":
            stream_result.content = parsed["content"]
            stream_result.tool_calls = []
        else:
            stream_result.content = ""
            stream_result.tool_calls = parsed["tool_calls"]
        yield LLMStreamChunk(event="result", result=stream_result)

    def tool_specs(self, registry: Any) -> list[dict[str, Any]]:
        return registry.prompt_tools()

    def summarize_turn(self, *, messages: list[dict[str, Any]]) -> LLMResult:
        return self.chat._chat(messages=self._normalize_messages(messages), tools=None, tool_choice=None)

    def summarize_turn_stream(self, *, messages: list[dict[str, Any]]) -> Iterator[LLMStreamChunk]:
        yield from self.chat._chat_stream(messages=self._normalize_messages(messages), tools=None, tool_choice=None)

    def assistant_plan_message(self, result: LLMResult) -> dict[str, Any]:
        return {
            "role": "user",
            "content": "<previous_tool_calls_already_executed>\n"
            + json.dumps(
                [{"id": call.id, "name": call.name, "arguments": call.arguments} for call in result.tool_calls],
                ensure_ascii=False,
            )
            + "\n</previous_tool_calls_already_executed>",
        }

    def tool_observation_messages(self, observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "role": "user",
                "content": (
                    f"<observation tool_call_id=\"{item['tool_call_id']}\" tool_name=\"{item['tool_name']}\">\n"
                    f"{json.dumps(item['observation'], ensure_ascii=False)}\n"
                    "</observation>"
                ),
            }
            for item in observations
        ]

    def _build_prompt_messages(self, *, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        protocol = {
            "role": "system",
            "content": (
                "<tool_protocol>\n"
                "你正在使用 XML+JSON 工具协议。只能调用 <available_tools> 中列出的工具。\n"
                "如果需要工具，只输出一个 <tool_calls> XML 块，块内必须是 JSON 数组。\n"
                "如果已有 observation 足够回答，只输出一个 <final_answer> XML 块，块内可以是中文 Markdown。\n"
                "同一轮只能输出 <tool_calls> 或 <final_answer> 之一；回复第一个字符必须是 <，不要输出任何前置说明。\n"
                "工具 arguments 必须是 JSON object；可以一次请求多个工具。\n"
                "</tool_protocol>\n"
                "<available_tools>\n"
                f"{json.dumps(tools, ensure_ascii=False)}\n"
                "</available_tools>\n"
                "<tool_call_format>\n"
                '<tool_calls>\n[{"id":"call_1","name":"available_tool_name","arguments":{}}]\n</tool_calls>\n'
                "</tool_call_format>\n"
                "<final_answer_format>\n<final_answer>\n最终中文回复\n</final_answer>\n</final_answer_format>"
            ),
        }
        return [protocol] + self._normalize_messages(messages)

    def _normalize_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for message in messages:
            role = message.get("role")
            if role == "tool":
                normalized.append(
                    {
                        "role": "user",
                        "content": (
                            f"<observation tool_call_id=\"{message.get('tool_call_id') or ''}\" "
                            f"tool_name=\"{message.get('name') or ''}\">\n"
                            f"{message.get('content') or ''}\n"
                            "</observation>"
                        ),
                    }
                )
                continue
            if role == "assistant" and message.get("tool_calls"):
                calls = []
                for item in message.get("tool_calls") or []:
                    function = item.get("function") or {}
                    raw_args = function.get("arguments") or "{}"
                    try:
                        args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                    except json.JSONDecodeError:
                        args = {}
                    calls.append({"id": item.get("id"), "name": function.get("name"), "arguments": args})
                normalized.append(
                    {
                        "role": "user",
                        "content": (
                            "<previous_tool_calls_already_executed>\n"
                            f"{json.dumps(calls, ensure_ascii=False)}\n"
                            "</previous_tool_calls_already_executed>"
                        ),
                    }
                )
                continue
            normalized.append({"role": role, "content": message.get("content") or ""})
        return normalized


def build_llm_provider(config: LLMConfig) -> LLMProvider:
    if config.provider == "openai_compatible":
        if config.tool_mode == "prompt_xml_json":
            return OpenAIPromptXmlJsonProvider(config)
        return OpenAINativeToolProvider(config)
    raise ValueError(f"Unsupported LLM provider: {config.provider}")
