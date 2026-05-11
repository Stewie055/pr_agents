from __future__ import annotations

import json

import httpx
import pytest

from semidiag.agent import AgentRuntime
from semidiag.agent.llm import LLMError, OpenAICompatibleProvider
from semidiag.config import LLMConfig
from semidiag.infrastructure.file_store import LocalFileStore
from semidiag.infrastructure.repository import SQLiteRepository


CSV_CONTENT = b"""timestamp,chamber_temperature,pressure,throughput
1,70,10,100
2,71,11,101
3,95,18,70
4,72,10,99
5,73,11,98
"""


def _runtime_with_provider(tmp_path, provider):
    repository = SQLiteRepository(tmp_path / "test.sqlite3")
    file_store = LocalFileStore(tmp_path / "files")
    case = repository.create_case("LLM chamber drift")
    dataset = file_store.save_bytes(
        case_id=case.id,
        filename="performance.csv",
        content=CSV_CONTENT,
        content_type="text/csv",
    )
    repository.add_dataset(dataset)
    return AgentRuntime(repository, llm=provider), repository, case, dataset


def test_openai_compatible_tool_call_flow(tmp_path):
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        requests.append(body)
        if "tools" in body:
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "",
                                "tool_calls": [
                                    {
                                        "id": "call_parse",
                                        "type": "function",
                                        "function": {
                                            "name": "parse_dataset",
                                            "arguments": json.dumps({"dataset_id": "placeholder"}),
                                        },
                                    },
                                    {
                                        "id": "call_profile",
                                        "type": "function",
                                        "function": {
                                            "name": "profile_dataset",
                                            "arguments": json.dumps({"dataset_id": "placeholder"}),
                                        },
                                    },
                                    {
                                        "id": "call_diag",
                                        "type": "function",
                                        "function": {"name": "diagnose_performance", "arguments": "{}"},
                                    },
                                ],
                            }
                        }
                    ]
                },
            )
        return httpx.Response(
            200,
            json={"choices": [{"message": {"role": "assistant", "content": "诊断完成，需工程师确认。"}}]},
        )

    provider = OpenAICompatibleProvider(
        LLMConfig(provider="openai_compatible", base_url="http://llm.test/v1", model="mock-model", api_key="secret")
    )
    provider.client = httpx.Client(transport=httpx.MockTransport(handler))
    runtime, repository, case, dataset = _runtime_with_provider(tmp_path, provider)

    result = runtime.handle_user_message(case_id=case.id, content="请诊断", dataset_id=dataset.id)

    assert result.message.content == "诊断完成，需工程师确认。"
    assert any(trace.tool_name == "diagnose_performance" for trace in result.tool_traces)
    assert len(repository.list_case_llm_audit_events(case.id)) == 2
    joined_request = json.dumps(requests, ensure_ascii=False)
    assert "timestamp,chamber_temperature" not in joined_request
    assert "Parsed 5 rows and 4 columns." in joined_request


def test_openai_compatible_invalid_tool_arguments_raise_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "tool_calls": [
                                {
                                    "id": "bad",
                                    "type": "function",
                                    "function": {"name": "parse_dataset", "arguments": "{not-json"},
                                }
                            ],
                        }
                    }
                ]
            },
        )

    provider = OpenAICompatibleProvider(LLMConfig(provider="openai_compatible", base_url="http://llm.test/v1"))
    provider.client = httpx.Client(transport=httpx.MockTransport(handler))

    with pytest.raises(LLMError, match="invalid tool arguments"):
        provider.plan_tool_calls(messages=[{"role": "user", "content": "x"}], tools=[])


def test_openai_compatible_http_error_is_mapped():
    provider = OpenAICompatibleProvider(LLMConfig(provider="openai_compatible", base_url="http://llm.test/v1"))
    provider.client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(500, text="boom")))

    with pytest.raises(LLMError, match="LLM HTTP error 500"):
        provider.plan_tool_calls(messages=[{"role": "user", "content": "x"}], tools=[])
