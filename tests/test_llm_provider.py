from __future__ import annotations

import json

import httpx
import pytest

from semidiag.agent import AgentRuntime
from semidiag.agent.llm import LLMError, OpenAINativeToolProvider, OpenAIPromptXmlJsonProvider, PromptXmlJsonParser
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
    tool_round = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal tool_round
        body = json.loads(request.content.decode())
        requests.append(body)
        if "路由器" in body["messages"][0]["content"]:
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": json.dumps(
                                    {
                                        "intent": "diagnosis",
                                        "requires_dataset": True,
                                        "requires_knowledge": False,
                                        "target_workflow": None,
                                        "user_goal": "诊断设备性能异常",
                                        "response_style": "normal",
                                        "reason": "用户要求诊断",
                                    }
                                ),
                            }
                        }
                    ]
                },
            )
        if "tools" in body:
            tool_round += 1
            if tool_round > 1:
                return httpx.Response(
                    200,
                    json={"choices": [{"message": {"role": "assistant", "content": "诊断完成，需工程师确认。"}}]},
                )
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "",
                                "reasoning_content": "Need to inspect metrics before diagnosis.",
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

    provider = OpenAINativeToolProvider(
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
    assert "Need to inspect metrics before diagnosis." in joined_request


def test_react_loop_can_continue_after_inspection(tmp_path):
    requests: list[dict] = []
    tool_round = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal tool_round
        body = json.loads(request.content.decode())
        requests.append(body)
        if "路由器" in body["messages"][0]["content"]:
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": json.dumps(
                                    {
                                        "intent": "diagnosis",
                                        "requires_dataset": True,
                                        "requires_knowledge": False,
                                        "target_workflow": None,
                                        "user_goal": "诊断设备性能异常",
                                        "response_style": "normal",
                                        "reason": "用户要求诊断",
                                    }
                                ),
                            }
                        }
                    ]
                },
            )
        if "tools" in body:
            tool_round += 1
            if tool_round == 1:
                return httpx.Response(
                    200,
                    json={
                        "choices": [
                            {
                                "message": {
                                    "role": "assistant",
                                    "content": "",
                                    "reasoning_content": "Need schema first.",
                                    "tool_calls": [
                                        {
                                            "id": "call_inspect",
                                            "type": "function",
                                            "function": {"name": "inspect_dataset", "arguments": "{}"},
                                        }
                                    ],
                                }
                            }
                        ]
                    },
                )
            if tool_round == 2:
                assert "chamber_temperature" in json.dumps(body, ensure_ascii=False)
                return httpx.Response(
                    200,
                    json={
                        "choices": [
                            {
                                "message": {
                                    "role": "assistant",
                                    "content": "",
                                    "reasoning_content": "Profile and diagnose.",
                                    "tool_calls": [
                                        {
                                            "id": "call_profile",
                                            "type": "function",
                                            "function": {"name": "profile_dataset", "arguments": "{}"},
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
                json={"choices": [{"message": {"role": "assistant", "content": "已完成多步诊断。"}}]},
            )
        return httpx.Response(500, text="unexpected")

    provider = OpenAINativeToolProvider(LLMConfig(provider="openai_compatible", base_url="http://llm.test/v1"))
    provider.client = httpx.Client(transport=httpx.MockTransport(handler))
    runtime, repository, case, dataset = _runtime_with_provider(tmp_path, provider)

    result = runtime.handle_user_message(case_id=case.id, content="请诊断", dataset_id=dataset.id)

    assert result.message.content == "已完成多步诊断。"
    assert [trace.tool_name for trace in result.tool_traces] == ["inspect_dataset", "profile_dataset", "diagnose_performance"]
    assert result.message.metadata["step_count"] == 3
    assert result.message.metadata["stop_reason"] == "final_answer"
    steps = repository.list_case_agent_step_traces(case.id)
    assert any("chamber_temperature" in json.dumps(step.observations, ensure_ascii=False) for step in steps)


def test_prompt_xml_json_tool_mode_runs_react_without_native_tools(tmp_path):
    requests: list[dict] = []
    tool_round = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal tool_round
        body = json.loads(request.content.decode())
        requests.append(body)
        if "路由器" in body["messages"][0]["content"]:
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": json.dumps(
                                    {
                                        "intent": "diagnosis",
                                        "requires_dataset": True,
                                        "requires_knowledge": False,
                                        "target_workflow": None,
                                        "user_goal": "诊断设备性能异常",
                                        "response_style": "normal",
                                        "reason": "用户要求诊断",
                                    }
                                ),
                            }
                        }
                    ]
                },
            )
        assert "tools" not in body
        assert "tool_choice" not in body
        assert "<available_tools>" in body["messages"][0]["content"]
        assert "inspect_dataset" in body["messages"][0]["content"]
        tool_round += 1
        if tool_round == 1:
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": (
                                    "<tool_calls>\n"
                                    + json.dumps(
                                        [
                                                {"id": "call_inspect", "name": "inspect_dataset", "arguments": {}},
                                                {"id": "call_profile", "name": "profile_dataset", "arguments": {}},
                                        ]
                                    )
                                    + "\n</tool_calls>"
                                ),
                            }
                        }
                    ]
                },
            )
        assert any("<observation" in item["content"] for item in body["messages"])
        previous_plan = [item for item in body["messages"] if "previous_tool_calls_already_executed" in item["content"]]
        assert previous_plan
        assert previous_plan[0]["role"] == "user"
        assert not any(item.get("role") == "tool" for item in body["messages"])
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "<final_answer>\n已完成 **prompt-xml-json** 诊断。\n</final_answer>",
                        }
                    }
                ]
            },
        )

    provider = OpenAIPromptXmlJsonProvider(
        LLMConfig(provider="openai_compatible", tool_mode="prompt_xml_json", base_url="http://llm.test/v1")
    )
    provider.client = httpx.Client(transport=httpx.MockTransport(handler))
    runtime, repository, case, dataset = _runtime_with_provider(tmp_path, provider)

    result = runtime.handle_user_message(case_id=case.id, content="请诊断", dataset_id=dataset.id)

    assert result.message.content == "已完成 **prompt-xml-json** 诊断。"
    assert [trace.tool_name for trace in result.tool_traces] == ["inspect_dataset", "profile_dataset"]
    assert result.message.metadata["llm_tool_mode"] == "prompt_xml_json"
    assert all("tools" not in request and "tool_choice" not in request for request in requests[1:])


def test_prompt_xml_json_tool_mode_rejects_invalid_xml():
    provider = OpenAIPromptXmlJsonProvider(
        LLMConfig(provider="openai_compatible", tool_mode="prompt_xml_json", base_url="http://llm.test/v1")
    )
    provider.client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": "not json"}}]})
        )
    )

    with pytest.raises(LLMError, match="tool_calls or final_answer"):
        provider.plan_tool_calls(messages=[{"role": "user", "content": "x"}], tools=[])


def test_prompt_xml_json_parser_rejects_ambiguous_or_invalid_payloads():
    with pytest.raises(LLMError, match="both tool_calls and final_answer"):
        PromptXmlJsonParser.parse("<tool_calls>[]</tool_calls><final_answer>x</final_answer>")
    with pytest.raises(LLMError, match="valid JSON"):
        PromptXmlJsonParser.parse("<tool_calls>{bad</tool_calls>")
    with pytest.raises(LLMError, match="non-empty JSON array"):
        PromptXmlJsonParser.parse("<tool_calls>[]</tool_calls>")
    with pytest.raises(LLMError, match="arguments must be an object"):
        PromptXmlJsonParser.parse('<tool_calls>[{"name":"inspect_dataset","arguments":[]}]</tool_calls>')


def test_prompt_xml_json_provider_repairs_malformed_first_output():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": "我先看一下"}}]})
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": '<tool_calls>[{"id":"call_1","name":"inspect_dataset","arguments":{}}]</tool_calls>',
                        }
                    }
                ]
            },
        )

    provider = OpenAIPromptXmlJsonProvider(
        LLMConfig(provider="openai_compatible", tool_mode="prompt_xml_json", base_url="http://llm.test/v1")
    )
    provider.client = httpx.Client(transport=httpx.MockTransport(handler))

    result = provider.plan_tool_calls(messages=[{"role": "user", "content": "x"}], tools=[])

    assert calls == 2
    assert result.tool_calls[0].name == "inspect_dataset"
    assert result.metadata["repair_reason"]


def test_react_loop_returns_tool_errors_as_observations(tmp_path):
    tool_round = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal tool_round
        body = json.loads(request.content.decode())
        if "路由器" in body["messages"][0]["content"]:
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": json.dumps(
                                    {
                                        "intent": "diagnosis",
                                        "requires_dataset": True,
                                        "requires_knowledge": False,
                                        "target_workflow": None,
                                        "user_goal": "诊断设备性能异常",
                                        "response_style": "normal",
                                        "reason": "用户要求诊断",
                                    }
                                ),
                            }
                        }
                    ]
                },
            )
        if "tools" in body:
            tool_round += 1
            if tool_round == 1:
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
                                            "id": "call_diag",
                                            "type": "function",
                                            "function": {"name": "diagnose_performance", "arguments": "{}"},
                                        }
                                    ],
                                }
                            }
                        ]
                    },
                )
            assert "profile_dataset must run before diagnose_performance" in json.dumps(body, ensure_ascii=False)
            return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": "需要先完成指标画像。"}}]})
        return httpx.Response(500, text="unexpected")

    provider = OpenAINativeToolProvider(LLMConfig(provider="openai_compatible", base_url="http://llm.test/v1"))
    provider.client = httpx.Client(transport=httpx.MockTransport(handler))
    runtime, repository, case, dataset = _runtime_with_provider(tmp_path, provider)

    result = runtime.handle_user_message(case_id=case.id, content="请诊断", dataset_id=dataset.id)

    assert result.message.content == "需要先完成指标画像。"
    steps = repository.list_case_agent_step_traces(case.id)
    assert any("profile_dataset must run before diagnose_performance" in json.dumps(step.observations, ensure_ascii=False) for step in steps)


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

    provider = OpenAINativeToolProvider(LLMConfig(provider="openai_compatible", base_url="http://llm.test/v1"))
    provider.client = httpx.Client(transport=httpx.MockTransport(handler))

    with pytest.raises(LLMError, match="invalid tool arguments"):
        provider.plan_tool_calls(messages=[{"role": "user", "content": "x"}], tools=[])


def test_openai_compatible_http_error_is_mapped():
    provider = OpenAINativeToolProvider(LLMConfig(provider="openai_compatible", base_url="http://llm.test/v1"))
    provider.client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(500, text="boom")))

    with pytest.raises(LLMError, match="LLM HTTP error 500"):
        provider.plan_tool_calls(messages=[{"role": "user", "content": "x"}], tools=[])


def test_runtime_returns_llm_content_when_no_tool_calls(tmp_path):
    call_index = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_index
        call_index += 1
        if call_index == 1:
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": json.dumps(
                                    {
                                        "intent": "chat_response",
                                        "requires_dataset": False,
                                        "requires_knowledge": False,
                                        "target_workflow": None,
                                        "user_goal": "用户问候",
                                        "response_style": "brief",
                                        "reason": "寒暄",
                                    }
                                ),
                            }
                        }
                    ]
                },
            )
        return httpx.Response(
            200,
            json={"choices": [{"message": {"role": "assistant", "content": "请先上传设备性能数据文件。"}}]},
        )

    provider = OpenAINativeToolProvider(LLMConfig(provider="openai_compatible", base_url="http://llm.test/v1"))
    provider.client = httpx.Client(transport=httpx.MockTransport(handler))
    repository = SQLiteRepository(tmp_path / "test.sqlite3")
    case = repository.create_case("No dataset")
    runtime = AgentRuntime(repository, llm=provider)

    result = runtime.handle_user_message(case_id=case.id, content="你好")

    assert result.message.content == "请先上传设备性能数据文件。"
    assert result.tool_traces == []


def test_diagnosis_without_dataset_is_blocked_after_llm_route(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(
                                {
                                    "intent": "diagnosis",
                                    "requires_dataset": True,
                                    "requires_knowledge": False,
                                    "target_workflow": None,
                                    "user_goal": "诊断设备异常",
                                    "response_style": "normal",
                                    "reason": "用户要求诊断",
                                }
                            ),
                        }
                    }
                ]
            },
        )

    provider = OpenAINativeToolProvider(LLMConfig(provider="openai_compatible", base_url="http://llm.test/v1"))
    provider.client = httpx.Client(transport=httpx.MockTransport(handler))
    repository = SQLiteRepository(tmp_path / "test.sqlite3")
    case = repository.create_case("No dataset")
    runtime = AgentRuntime(repository, llm=provider)

    result = runtime.handle_user_message(case_id=case.id, content="请诊断")

    assert "请先上传 CSV 文件" in result.message.content
    assert result.message.metadata["intent"] == "diagnosis"
    assert result.message.metadata["blocked_by_state_gate"] is True
    assert result.tool_traces == []


def test_user_visible_response_sanitizes_internal_ids(tmp_path):
    call_index = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_index
        call_index += 1
        if call_index == 1:
            content = json.dumps(
                {
                    "intent": "chat_response",
                    "requires_dataset": False,
                    "requires_knowledge": False,
                    "target_workflow": None,
                    "user_goal": "用户问候",
                    "response_style": "brief",
                    "reason": "寒暄",
                }
            )
        else:
            content = "当前 case_secret123 可以使用 ds_secret456，结果见 art_secret789。"
        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": content}}]})

    provider = OpenAINativeToolProvider(LLMConfig(provider="openai_compatible", base_url="http://llm.test/v1"))
    provider.client = httpx.Client(transport=httpx.MockTransport(handler))
    repository = SQLiteRepository(tmp_path / "test.sqlite3")
    case = repository.create_case("ID sanitize")
    runtime = AgentRuntime(repository, llm=provider)

    result = runtime.handle_user_message(case_id=case.id, content="你好")

    assert "case_secret123" not in result.message.content
    assert "ds_secret456" not in result.message.content
    assert "art_secret789" not in result.message.content


def test_user_visible_response_removes_tool_call_markup(tmp_path):
    call_index = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_index
        call_index += 1
        if call_index == 1:
            content = json.dumps(
                {
                    "intent": "diagnosis",
                    "requires_dataset": True,
                    "requires_knowledge": False,
                    "target_workflow": None,
                    "user_goal": "诊断设备异常",
                    "response_style": "normal",
                    "reason": "用户要求诊断",
                }
            )
        elif call_index == 2:
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "",
                                "reasoning_content": "Use metrics.",
                                "tool_calls": [
                                    {
                                        "id": "call_parse",
                                        "type": "function",
                                        "function": {"name": "parse_dataset", "arguments": "{}"},
                                    }
                                ],
                            }
                        }
                    ]
                },
            )
        else:
            content = "已完成解析。\n<｜｜DSML｜｜tool_calls><｜｜DSML｜｜invoke name=\"x\"></｜｜DSML｜｜invoke></｜｜DSML｜｜tool_calls>"
        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": content}}]})

    provider = OpenAINativeToolProvider(LLMConfig(provider="openai_compatible", base_url="http://llm.test/v1"))
    provider.client = httpx.Client(transport=httpx.MockTransport(handler))
    runtime, repository, case, dataset = _runtime_with_provider(tmp_path, provider)

    result = runtime.handle_user_message(case_id=case.id, content="请诊断", dataset_id=dataset.id)

    assert "已完成解析" in result.message.content
    assert "DSML" not in result.message.content
    assert "tool_calls" not in result.message.content
