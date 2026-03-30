import json
from pathlib import Path

from fastapi.testclient import TestClient

from pr_agents.bootstrap import build_api_app, build_components
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

    task_service, _ = build_components(build_test_settings(tmp_path))
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


def test_webui_homepage_serves_frontend_or_build_hint(tmp_path: Path) -> None:
    app = build_api_app(build_test_settings(tmp_path))
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code in {200, 503}
    if response.status_code == 200:
        assert '<div id="root"></div>' in response.text
        assert "/assets/" in response.text
        assert "pr_agents Diagnostic Agent" in response.text
    else:
        assert "frontend not built" in response.text
        assert "/api/v1" in response.text


def test_chart_artifact_raw_endpoint_returns_svg(tmp_path: Path) -> None:
    app = build_api_app(build_test_settings(tmp_path))
    client = TestClient(app)

    response = client.post(
        "/api/v1/tasks/file-analysis",
        json={
            "business_code": "A_DEMO",
            "objective": "Generate a scientific plot report for the demo dataset",
            "file_name": "demo_a.csv",
            "content": "temperature,pressure\n21.5,101.2\n22.1,101.5\n22.8,101.7\n",
            "chart_profile": {"chart_type": "scientific_plot"},
        },
    )

    chart_artifact_id = response.json()["result"]["chart"]["artifact"]["artifact_id"]
    raw_response = client.get(f"/api/v1/artifacts/{chart_artifact_id}/raw")

    assert raw_response.status_code == 200
    assert raw_response.headers["content-type"].startswith("image/svg+xml")
    assert "<svg" in raw_response.text


def test_agent_session_chat_flow_and_follow_up_report(tmp_path: Path) -> None:
    app = build_api_app(build_test_settings(tmp_path))
    client = TestClient(app)

    create_response = client.post("/api/v1/agent/sessions")
    assert create_response.status_code == 200
    session_id = create_response.json()["session_id"]

    source_response = client.post(
        f"/api/v1/agent/sessions/{session_id}/demo-sources/a_demo_file",
    )
    assert source_response.status_code == 200
    source_id = source_response.json()["source_id"]

    start_response = client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={
            "content": "Please use A_DEMO file data to generate a scientific plot and report.",
            "source_id": source_id,
        },
    )
    assert start_response.status_code == 200
    start_payload = start_response.json()
    assert start_payload["session_id"] == session_id
    events = consume_sse(client, start_payload["stream_url"])
    event_names = [event["event"] for event in events]
    assert "run_started" in event_names
    assert "tool_called" in event_names
    assert "step_started" in event_names
    assert "tool_result" in event_names
    assert "assistant_started" in event_names
    assert "assistant_delta" in event_names
    assert "assistant_completed" in event_names
    assert "run_completed" in event_names
    run_started_event = next(event for event in events if event["event"] == "run_started")
    assert "prompt_snapshot" in run_started_event["data"]["data"]["debug"]
    assert "memory_snapshot" in run_started_event["data"]["data"]["debug"]

    payload = client.get(f"/api/v1/agent/sessions/{session_id}").json()
    assert payload["runs"]
    assert payload["runs"][0]["steps"]
    assert payload["sources"]
    assert "prompt_snapshot" in payload["runs"][0]["metadata"]
    assert "memory_snapshot" in payload["runs"][0]["metadata"]
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
    assert any(event["event"] == "tool_called" for event in follow_up_events)
    assert any(event["event"] == "assistant_completed" for event in follow_up_events)
    follow_up_payload = client.get(f"/api/v1/agent/sessions/{session_id}").json()
    assert len(follow_up_payload["messages"]) > len(payload["messages"])
    assert "business_code=A_DEMO" in follow_up_payload["messages"][-1]["content"]

    summary_follow_up = client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={"content": "Please summarize the report key points."},
    )
    assert summary_follow_up.status_code == 200
    summary_events = consume_sse(client, summary_follow_up.json()["stream_url"])
    assert any(event["event"] == "tool_called" for event in summary_events)
    assert any(event["event"] == "assistant_completed" for event in summary_events)
    summary_payload = client.get(f"/api/v1/agent/sessions/{session_id}").json()
    summary_message = summary_payload["messages"][-1]
    assert "Summary for A_DEMO:" in summary_message["content"]
    assert summary_message["metadata"]["summary_only"] is True
    assert summary_message["metadata"]["report_preview"].startswith("# ")


def test_agent_session_database_demo_flow(tmp_path: Path) -> None:
    app = build_api_app(build_test_settings(tmp_path))
    client = TestClient(app)

    session_id = client.post("/api/v1/agent/sessions").json()["session_id"]
    source_id = client.post(
        f"/api/v1/agent/sessions/{session_id}/demo-sources/a_demo_db",
    ).json()["source_id"]
    start_payload = client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={
            "content": "Please use database data to generate a scientific plot and report for A_DEMO.",
            "source_id": source_id,
        },
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

    assert not any(msg["message_type"] == "tool_call" for msg in payload["messages"])
    assert payload["tasks"] == []
    assert any(event["event"] == "assistant_completed" for event in events)
    assert any(event["event"] == "assistant_delta" for event in events)
    assert not any(event["event"] == "tool_called" for event in events)
    assert "你好" in payload["messages"][-1]["content"] or "A_DEMO" in payload["messages"][-1]["content"]


def test_agent_session_artifact_proxy_reads_report(tmp_path: Path) -> None:
    app = build_api_app(build_test_settings(tmp_path))
    client = TestClient(app)

    session_id = client.post("/api/v1/agent/sessions").json()["session_id"]
    source_id = client.post(
        f"/api/v1/agent/sessions/{session_id}/demo-sources/a_demo_file",
    ).json()["source_id"]
    start_payload = client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={
            "content": "Please use A_DEMO file data to generate a scientific plot and report.",
            "source_id": source_id,
        },
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


def test_agent_run_control_endpoints_update_run_metadata(tmp_path: Path) -> None:
    app = build_api_app(build_test_settings(tmp_path))
    client = TestClient(app)

    session_id = client.post("/api/v1/agent/sessions").json()["session_id"]
    start_payload = client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={"content": "Please use A_DEMO file data to generate a scientific plot and report."},
    ).json()
    run_id = start_payload["run_id"]

    pause_response = client.post(
        f"/api/v1/agent/sessions/{session_id}/runs/{run_id}/control",
        json={"action": "pause", "note": "pause for inspection"},
    )
    assert pause_response.status_code == 200
    assert pause_response.json()["control_state"] == "paused"

    rerun_response = client.post(
        f"/api/v1/agent/sessions/{session_id}/runs/{run_id}/control",
        json={"action": "rerun_step", "step_id": "step-demo", "note": "rerun the last step"},
    )
    assert rerun_response.status_code == 200
    assert rerun_response.json()["applied"] is True
    assert rerun_response.json()["message"] == "Rerun started."
    assert rerun_response.json()["spawned_run_id"] is not None
    assert rerun_response.json()["stream_url"] is not None

    rerun_events = consume_sse(client, rerun_response.json()["stream_url"])
    rerun_event_names = [event["event"] for event in rerun_events]
    assert "run_started" in rerun_event_names
    assert "tool_called" in rerun_event_names
    assert "run_completed" in rerun_event_names

    modify_response = client.post(
        f"/api/v1/agent/sessions/{session_id}/runs/{run_id}/control",
        json={
            "action": "modify_state",
            "note": "manual review",
            "state_patch": {"manual_review": True},
        },
    )
    assert modify_response.status_code == 200
    assert modify_response.json()["applied"] is True

    resume_response = client.post(
        f"/api/v1/agent/sessions/{session_id}/runs/{run_id}/control",
        json={"action": "resume", "note": "continue"},
    )
    assert resume_response.status_code == 200
    assert resume_response.json()["control_state"] == "running"

    payload = client.get(f"/api/v1/agent/sessions/{session_id}").json()
    original_run = next(run for run in payload["runs"] if run["run_id"] == run_id)
    rerun = next(run for run in payload["runs"] if run["run_id"] == rerun_response.json()["spawned_run_id"])
    assert original_run["metadata"]["control_state"] == "running"
    assert original_run["metadata"]["last_control_action"] == "modify_state"
    assert original_run["metadata"]["last_state_patch"]["manual_review"] is True
    assert rerun["metadata"]["rerun_source_run_id"] == run_id


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


def test_agent_source_registration_and_listing(tmp_path: Path) -> None:
    app = build_api_app(build_test_settings(tmp_path))
    client = TestClient(app)

    session_id = client.post("/api/v1/agent/sessions").json()["session_id"]
    register_response = client.post(
        f"/api/v1/agent/sessions/{session_id}/sources/file",
        json={"file_name": "demo.csv", "content": "a,b\n1,2\n", "source_profile": {"source_pattern": "per_business_file"}},
    )

    assert register_response.status_code == 200
    source_payload = register_response.json()
    assert source_payload["source_type"] == "file"

    list_response = client.get(f"/api/v1/agent/sessions/{session_id}/sources")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1


def test_agent_message_without_source_returns_guidance(tmp_path: Path) -> None:
    app = build_api_app(build_test_settings(tmp_path))
    client = TestClient(app)

    session_id = client.post("/api/v1/agent/sessions").json()["session_id"]
    start_payload = client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={"content": "Please use A_DEMO file data to generate a scientific plot and report."},
    ).json()
    events = consume_sse(client, start_payload["stream_url"])

    assert any(event["event"] == "step_failed" for event in events)
    completed = next(event for event in events if event["event"] == "assistant_completed")
    assert "Register a file source" in completed["data"]["data"]["message"]
