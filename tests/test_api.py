import json
from pathlib import Path

from fastapi.testclient import TestClient

from pr_agents.agent.llm import GLMProvider
from pr_agents.api.app import create_api_app
from pr_agents.bootstrap import build_api_app
from pr_agents.bootstrap import build_components
from pr_agents.models import IntentMode
from pr_agents.settings import Settings


def build_test_settings(tmp_path: Path) -> Settings:
    return Settings(
        artifact_base_dir=str(tmp_path / "artifacts"),
        sqlite_path=str(tmp_path / "artifacts" / "app.db"),
        intent_mode=IntentMode.FAKE,
    )


def consume_sse(client: TestClient, url: str) -> list[dict]:
    events: list[dict] = []
    with client.stream("GET", url) as response:
        assert response.status_code == 200
        event_name = None
        data = None
        for line in response.iter_lines():
            if not line:
                if event_name and data:
                    events.append({"event": event_name, "data": json.loads(data)})
                event_name = None
                data = None
                continue
            if line.startswith("event: "):
                event_name = line[len("event: ") :]
            elif line.startswith("data: "):
                data = line[len("data: ") :]
    return events


def test_file_analysis_api_and_task_queries(tmp_path: Path) -> None:
    app = build_api_app(build_test_settings(tmp_path))
    client = TestClient(app)

    response = client.post(
        "/api/v1/tasks/file-analysis",
        json={
            "business_code": "A001",
            "objective": "prepare report",
            "file_name": "demo.csv",
            "content": "a,b\n1,2\n",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "succeeded"
    task_id = payload["task_id"]
    session_id = payload["session_id"]

    task_response = client.get(f"/api/v1/tasks/{task_id}")
    assert task_response.status_code == 200
    task_payload = task_response.json()
    assert task_payload["task"]["status"] == "succeeded"
    assert task_payload["task"]["input_summary"]["business_code"] == "A001"
    assert len(task_payload["artifacts"]) == 3

    session_response = client.get(f"/api/v1/sessions/{session_id}/tasks")
    assert session_response.status_code == 200
    assert len(session_response.json()["tasks"]) == 1

    artifact_id = task_payload["artifacts"][2]["artifact_id"]
    artifact_response = client.get(f"/api/v1/artifacts/{artifact_id}")
    assert artifact_response.status_code == 200
    content_response = client.get(f"/api/v1/artifacts/{artifact_id}/content")
    assert content_response.status_code == 200
    assert "Analysis completed" in content_response.text


def test_missing_resources_return_404(tmp_path: Path) -> None:
    app = build_api_app(build_test_settings(tmp_path))
    client = TestClient(app)

    assert client.get("/api/v1/tasks/unknown").status_code == 404
    assert client.get("/api/v1/artifacts/unknown").status_code == 404


def test_non_text_artifact_returns_415(tmp_path: Path) -> None:
    app = build_api_app(build_test_settings(tmp_path))
    client = TestClient(app)

    response = client.post(
        "/api/v1/tasks/file-analysis",
        json={
            "business_code": "A001",
            "objective": "prepare report",
            "file_name": "demo.csv",
            "content": "a,b\n1,2\n",
        },
    )
    artifact_id = response.json()["result"]["chart"]["artifact"]["artifact_id"]
    binary_path = tmp_path / "artifacts" / "binary.bin"
    binary_path.write_bytes(b"\x00\x01")

    artifact_response = client.get(f"/api/v1/artifacts/{artifact_id}")
    assert artifact_response.status_code == 200

    from pr_agents.bootstrap import build_components

    _, task_service, _ = build_components(
        build_test_settings(tmp_path)
    )
    artifact = task_service.get_artifact(artifact_id)
    assert artifact is not None
    artifact.uri = str(binary_path)
    task_service.artifact_repository.register_artifact(
        task_id=artifact.task_id,
        artifact_type=artifact.artifact_type,
        uri=artifact.uri,
        filename=binary_path.name,
        metadata={"artifact_id": artifact.artifact_id},
    )

    unsupported = client.get(f"/api/v1/artifacts/{artifact_id}/content")
    assert unsupported.status_code == 415


def test_shared_file_business_mode_and_scientific_plot(tmp_path: Path) -> None:
    app = build_api_app(build_test_settings(tmp_path))
    client = TestClient(app)

    response = client.post(
        "/api/v1/tasks/file-analysis",
        json={
            "business_code": "B001",
            "objective": "prepare scientific report",
            "file_name": "shared.csv",
            "content": "business_code,value\nB001,1\nB002,2\nB001,3\n",
            "source_profile": {"source_pattern": "shared_file"},
            "chart_profile": {"chart_type": "scientific_plot"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["dataset"]["row_count"] == 2
    assert payload["result"]["chart"]["chart_type"] == "scientific_plot"
    assert payload["result"]["dataset"]["metadata"]["business_code"] == "B001"


def test_official_a_demo_flow_returns_scientific_plot_and_report(tmp_path: Path) -> None:
    app = build_api_app(build_test_settings(tmp_path))
    client = TestClient(app)

    response = client.post(
        "/api/v1/tasks/file-analysis",
        json={
            "business_code": "A_DEMO",
            "objective": "Generate a scientific plot report for the demo dataset",
            "file_name": "demo_a.csv",
            "content": "temperature,pressure\n21.5,101.2\n22.1,101.5\n22.8,101.7\n",
            "source_profile": {"source_pattern": "per_business_file", "data_version": "demo-v1"},
            "chart_profile": {"chart_type": "scientific_plot"},
            "report_profile": {"template": "demo-template"},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "succeeded"
    assert payload["result"]["chart"]["chart_type"] == "scientific_plot"
    assert payload["result"]["report"] is not None

    task_id = payload["task_id"]
    task_payload = client.get(f"/api/v1/tasks/{task_id}").json()
    report_artifact = next(
        artifact for artifact in task_payload["artifacts"] if artifact["artifact_type"] == "report"
    )
    report_content = client.get(f"/api/v1/artifacts/{report_artifact['artifact_id']}/content")

    assert report_content.status_code == 200
    assert "business_code=A_DEMO" in report_content.text
    assert "Generate a scientific plot report for the demo dataset" in report_content.text


def test_webui_homepage_contains_chat_demo(tmp_path: Path) -> None:
    app = build_api_app(build_test_settings(tmp_path))
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "Agent Workspace" in response.text
    assert "New chat" in response.text
    assert "session-list" in response.text
    assert "prompt" in response.text
    assert "Run File Demo" in response.text
    assert "Run DB Demo" in response.text
    assert "Summarize report" in response.text
    assert "/api/v1/agent/sessions" in response.text
    assert "EventSource" in response.text
    assert "Queued..." in response.text
    assert "Task details" in response.text
    assert "report_preview" in response.text
    assert "filter(function (message)" in response.text
    assert "Intent mode:" in response.text


def test_agent_session_chat_flow_and_follow_up_report(tmp_path: Path) -> None:
    app = build_api_app(build_test_settings(tmp_path))
    client = TestClient(app)

    create_response = client.post("/api/v1/agent/sessions")
    assert create_response.status_code == 200
    session_id = create_response.json()["session_id"]

    start_response = client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={"content": "Please use A_DEMO file data to generate a scientific plot and report."},
    )
    assert start_response.status_code == 200
    start_payload = start_response.json()
    assert start_payload["session_id"] == session_id
    events = consume_sse(client, start_payload["stream_url"])
    event_names = [event["event"] for event in events]
    assert "run_started" in event_names
    assert "planning_started" in event_names
    assert "plan_created" in event_names
    assert "tool_called" in event_names
    assert "run_completed" in event_names

    payload = client.get(f"/api/v1/agent/sessions/{session_id}").json()
    assert any(msg["message_type"] == "plan" for msg in payload["messages"])
    assert any(msg["message_type"] == "tool_call" for msg in payload["messages"])
    assert payload["runs"]
    assert payload["runs"][0]["steps"]
    plan_message = next(msg for msg in payload["messages"] if msg["message_type"] == "plan")
    assert plan_message["metadata"]["intent_mode"] == "fake"
    assert plan_message["metadata"]["planner_source"] == "fake"
    result_message = next(
        msg for msg in payload["messages"] if msg["role"] == "assistant" and msg["metadata"].get("task_id")
    )
    assert "scientific_plot" in result_message["content"]
    assert "business_code=A_DEMO" not in result_message["content"]
    assert result_message["metadata"]["report_preview"].startswith("# ")

    follow_up_start = client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={"content": "Show me the report again."},
    )
    assert follow_up_start.status_code == 200
    follow_up_events = consume_sse(client, follow_up_start.json()["stream_url"])
    assert any(event["event"] == "chat_reply" for event in follow_up_events)
    follow_up_payload = client.get(f"/api/v1/agent/sessions/{session_id}").json()
    assert len(follow_up_payload["messages"]) > len(payload["messages"])
    assert "business_code=A_DEMO" in follow_up_payload["messages"][-1]["content"]

    summary_follow_up = client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={"content": "Please summarize the report key points."},
    )
    assert summary_follow_up.status_code == 200
    summary_events = consume_sse(client, summary_follow_up.json()["stream_url"])
    assert any(event["event"] == "chat_reply" for event in summary_events)
    summary_payload = client.get(f"/api/v1/agent/sessions/{session_id}").json()
    summary_message = summary_payload["messages"][-1]
    assert "Summary for A_DEMO:" in summary_message["content"]
    assert summary_message["metadata"]["summary_only"] is True
    assert summary_message["metadata"]["report_preview"].startswith("# ")


def test_agent_session_database_demo_flow(tmp_path: Path) -> None:
    app = build_api_app(build_test_settings(tmp_path))
    client = TestClient(app)

    session_id = client.post("/api/v1/agent/sessions").json()["session_id"]
    start_payload = client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={"content": "Please use database data to generate a scientific plot and report for A_DEMO."},
    ).json()
    events = consume_sse(client, start_payload["stream_url"])
    payload = client.get(f"/api/v1/agent/sessions/{session_id}").json()

    assert any(event["event"] == "tool_called" for event in events)
    assert payload["tasks"]
    assert payload["tasks"][0]["task_type"] == "db_analysis"
    run = payload["runs"][0]
    assert run["steps"][0]["tool_name"] == "run_db_analysis_workflow"
    result_message = next(
        msg for msg in payload["messages"] if msg["role"] == "assistant" and msg["metadata"].get("task_id")
    )
    assert "scientific_plot" in result_message["content"]


def test_agent_session_chat_message_does_not_trigger_plan_or_tool(tmp_path: Path) -> None:
    app = build_api_app(build_test_settings(tmp_path))
    client = TestClient(app)

    session_id = client.post("/api/v1/agent/sessions").json()["session_id"]
    start_payload = client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={"content": "你好"},
    ).json()
    events = consume_sse(client, start_payload["stream_url"])
    payload = client.get(f"/api/v1/agent/sessions/{session_id}").json()

    assert not any(msg["message_type"] == "plan" for msg in payload["messages"])
    assert not any(msg["message_type"] == "tool_call" for msg in payload["messages"])
    assert payload["tasks"] == []
    assert any(event["event"] == "chat_reply" for event in events)
    assert not any(event["event"] == "tool_called" for event in events)
    assert "你好" in payload["messages"][-1]["content"] or "A_DEMO" in payload["messages"][-1]["content"]


def test_agent_session_artifact_proxy_reads_report(tmp_path: Path) -> None:
    app = build_api_app(build_test_settings(tmp_path))
    client = TestClient(app)

    session_id = client.post("/api/v1/agent/sessions").json()["session_id"]
    start_payload = client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={"content": "Please use A_DEMO file data to generate a scientific plot and report."},
    ).json()
    consume_sse(client, start_payload["stream_url"])
    payload = client.get(f"/api/v1/agent/sessions/{session_id}").json()
    task_with_result = next(task for task in payload["tasks"] if task["status"] == "succeeded")
    task_detail = client.get(f"/api/v1/tasks/{task_with_result['task_id']}").json()
    report_artifact = next(
        artifact for artifact in task_detail["artifacts"] if artifact["artifact_type"] == "report"
    )

    report_response = client.get(
        f"/api/v1/agent/sessions/{session_id}/artifacts/{report_artifact['artifact_id']}/content"
    )

    assert report_response.status_code == 200
    assert "Analysis completed" in report_response.text


def test_task_result_is_restored_after_rebuilding_services(tmp_path: Path) -> None:
    settings = build_test_settings(tmp_path)
    app = build_api_app(settings)
    client = TestClient(app)

    response = client.post(
        "/api/v1/tasks/file-analysis",
        json={
            "business_code": "A_DEMO",
            "objective": "Generate a scientific plot report for the demo dataset",
            "file_name": "demo_a.csv",
            "content": "temperature,pressure\n21.5,101.2\n22.1,101.5\n22.8,101.7\n",
            "source_profile": {"source_pattern": "per_business_file", "data_version": "demo-v1"},
            "chart_profile": {"chart_type": "scientific_plot"},
            "report_profile": {"template": "demo-template"},
        },
    )
    task_id = response.json()["task_id"]

    rebuilt_app = build_api_app(settings)
    rebuilt_client = TestClient(rebuilt_app)
    task_detail = rebuilt_client.get(f"/api/v1/tasks/{task_id}")

    assert task_detail.status_code == 200
    payload = task_detail.json()
    assert payload["result"] is not None
    assert payload["result"]["report"] is not None
    assert payload["result"]["chart"]["chart_type"] == "scientific_plot"


def test_agent_session_uses_llm_mode_with_fallback_llm(tmp_path: Path) -> None:
    settings = build_test_settings(tmp_path)
    webui, task_service, agent_session_service = build_components(settings)
    del webui
    decision_provider = GLMProvider(
        base_url="https://glm.example.com/v1",
        api_key="secret",
        requester=lambda _url, _payload, _headers, _timeout: json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"action":"call_tool","tool_name":"run_file_analysis_workflow",'
                                '"tool_input":{"business_code":"A_DEMO","entry":"file","objective":"Please analyze A_DEMO with the model.","chart_type":"scientific_plot"},'
                                '"response":"","thought_summary":"Run the file workflow."}'
                            )
                        }
                    }
                ]
            }
        ),
    )
    planner_provider = GLMProvider(
        base_url="https://glm.example.com/v1",
        api_key="secret",
        requester=lambda _url, _payload, _headers, _timeout: json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"goal":"Please analyze A_DEMO with the model.",'
                                '"business_code":"A_DEMO",'
                                '"entry":"file",'
                                '"steps":['
                                '{"step_index":0,"title":"Run file analysis workflow for A_DEMO",'
                                '"tool_name":"run_file_analysis_workflow","inputs_summary":{"business_code":"A_DEMO"}},'
                                '{"step_index":1,"title":"Summarize workflow results for the user",'
                                '"tool_name":"summarize_session_results","inputs_summary":{"goal":"Please analyze A_DEMO with the model."}}'
                                '],'
                                '"expected_outputs":["chart","report"],'
                                '"planner_source":"llm","used_fallback":false}'
                            )
                        }
                    }
                ]
            }
        ),
    )
    agent_session_service.runtime.react_agent.llm = decision_provider
    agent_session_service.runtime.react_agent.mode = "llm"
    agent_session_service.runtime.planner_agent.llm = planner_provider
    agent_session_service.runtime.planner_agent.mode = "llm"
    app = create_api_app(task_service, agent_session_service)
    client = TestClient(app)

    session_id = client.post("/api/v1/agent/sessions").json()["session_id"]
    start_payload = client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={"content": "Please analyze A_DEMO with the model."},
    ).json()
    events = consume_sse(client, start_payload["stream_url"])
    payload = client.get(f"/api/v1/agent/sessions/{session_id}").json()

    plan_message = next(msg for msg in payload["messages"] if msg["message_type"] == "plan")
    assert plan_message["metadata"]["intent_mode"] == "llm"
    assert payload["runs"][0]["metadata"]["planner_source"] in {"llm", "llm_fallback"}
    assert payload["runs"][0]["metadata"]["decision_source"] in {"llm", "llm_fallback"}
    assert any(event["event"] == "plan_created" for event in events)


def test_agent_session_rejects_non_allowed_llm_tool_and_returns_response(tmp_path: Path) -> None:
    settings = build_test_settings(tmp_path)
    webui, task_service, agent_session_service = build_components(settings)
    del webui
    agent_session_service.runtime.react_agent.llm = GLMProvider(
        base_url="https://glm.example.com/v1",
        api_key="secret",
        requester=lambda _url, _payload, _headers, _timeout: json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"action":"call_tool","tool_name":"unsafe_tool",'
                                '"tool_input":{},"response":"","thought_summary":"Try a disallowed tool."}'
                            )
                        }
                    }
                ]
            }
        ),
    )
    agent_session_service.runtime.react_agent.mode = "llm"
    app = create_api_app(task_service, agent_session_service)
    client = TestClient(app)

    session_id = client.post("/api/v1/agent/sessions").json()["session_id"]
    start_payload = client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={"content": "Please use A_DEMO file data to generate a scientific plot and report."},
    ).json()
    events = consume_sse(client, start_payload["stream_url"])
    payload = client.get(f"/api/v1/agent/sessions/{session_id}").json()

    assert not any(msg["message_type"] == "plan" for msg in payload["messages"])
    assert payload["tasks"] == []
    assert any(event["event"] == "chat_reply" for event in events)
