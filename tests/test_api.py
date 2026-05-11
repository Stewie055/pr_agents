from __future__ import annotations

from fastapi.testclient import TestClient

from semidiag.agent import AgentRuntime
from semidiag.agent.llm import StubLLMProvider
from semidiag.api.main import AppState, create_app
from semidiag.tools import build_default_registry


CSV_CONTENT = """timestamp,chamber_temperature,pressure,throughput
1,70,10,100
2,71,11,101
3,95,18,70
4,72,10,99
5,73,11,98
"""


def test_api_case_upload_and_agent_message(tmp_path):
    state = AppState(tmp_path)
    state.agent = AgentRuntime(state.repository, registry=build_default_registry(), llm=StubLLMProvider())
    app = create_app(state)
    client = TestClient(app)

    created = client.post("/api/cases", json={"title": "Chamber drift"}).json()
    case_id = created["id"]

    upload = client.post(
        f"/api/cases/{case_id}/files",
        files={"file": ("performance.csv", CSV_CONTENT, "text/csv")},
    )
    assert upload.status_code == 200
    dataset_id = upload.json()["id"]

    response = client.post(
        f"/api/cases/{case_id}/messages",
        json={"content": "请分析并诊断", "dataset_id": dataset_id},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["message"]["role"] == "assistant"
    assert any(item["kind"] == "diagnosis" for item in body["artifacts"])
    assert any(trace["tool_name"] == "diagnose_performance" for trace in body["tool_traces"])


def test_api_lists_tool_contracts(tmp_path):
    state = AppState(tmp_path)
    state.agent = AgentRuntime(state.repository, registry=build_default_registry(), llm=StubLLMProvider())
    app = create_app(state)
    client = TestClient(app)

    response = client.get("/api/tools")

    assert response.status_code == 200
    names = {tool["name"] for tool in response.json()["tools"]}
    assert {"parse_dataset", "profile_dataset", "diagnose_performance", "generate_report"} <= names
