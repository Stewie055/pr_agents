from __future__ import annotations

from fastapi.testclient import TestClient

from semidiag.agent import AgentRuntime
from semidiag.agent.llm import LLMError, LLMResult
from semidiag.api.main import AppState, create_app
from semidiag.tools import build_default_registry


class FailingProvider:
    provider_name = "openai_compatible"
    model = "failing-model"

    def plan_tool_calls(self, *, messages, tools):
        raise LLMError("mock llm down", status_code=502)

    def summarize_turn(self, *, messages):
        raise LLMError("mock llm down", status_code=502)


def test_api_returns_llm_error(tmp_path):
    state = AppState(tmp_path)
    state.agent = AgentRuntime(state.repository, registry=build_default_registry(), llm=FailingProvider())
    app = create_app(state)
    client = TestClient(app)
    case = client.post("/api/cases", json={"title": "LLM failure"}).json()

    response = client.post(f"/api/cases/{case['id']}/messages", json={"content": "请诊断"})

    assert response.status_code == 502
    assert response.json()["detail"] == "mock llm down"
