from pathlib import Path

from fastapi.testclient import TestClient

from pr_agents.bootstrap import build_api_app
from pr_agents.settings import Settings


def test_file_analysis_api_and_task_queries(tmp_path: Path) -> None:
    app = build_api_app(
        Settings(
            artifact_base_dir=str(tmp_path / "artifacts"),
            sqlite_path=str(tmp_path / "artifacts" / "app.db"),
        )
    )
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
    app = build_api_app(
        Settings(
            artifact_base_dir=str(tmp_path / "artifacts"),
            sqlite_path=str(tmp_path / "artifacts" / "app.db"),
        )
    )
    client = TestClient(app)

    assert client.get("/api/v1/tasks/unknown").status_code == 404
    assert client.get("/api/v1/artifacts/unknown").status_code == 404


def test_non_text_artifact_returns_415(tmp_path: Path) -> None:
    app = build_api_app(
        Settings(
            artifact_base_dir=str(tmp_path / "artifacts"),
            sqlite_path=str(tmp_path / "artifacts" / "app.db"),
        )
    )
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
        Settings(
            artifact_base_dir=str(tmp_path / "artifacts"),
            sqlite_path=str(tmp_path / "artifacts" / "app.db"),
        )
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
    app = build_api_app(
        Settings(
            artifact_base_dir=str(tmp_path / "artifacts"),
            sqlite_path=str(tmp_path / "artifacts" / "app.db"),
        )
    )
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
    app = build_api_app(
        Settings(
            artifact_base_dir=str(tmp_path / "artifacts"),
            sqlite_path=str(tmp_path / "artifacts" / "app.db"),
        )
    )
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
    app = build_api_app(
        Settings(
            artifact_base_dir=str(tmp_path / "artifacts"),
            sqlite_path=str(tmp_path / "artifacts" / "app.db"),
        )
    )
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "Agent Workspace" in response.text
    assert "New chat" in response.text
    assert "session-list" in response.text
    assert "prompt" in response.text
    assert "Run A_DEMO" in response.text
    assert "/api/v1/agent/sessions" in response.text


def test_agent_session_chat_flow_and_follow_up_report(tmp_path: Path) -> None:
    app = build_api_app(
        Settings(
            artifact_base_dir=str(tmp_path / "artifacts"),
            sqlite_path=str(tmp_path / "artifacts" / "app.db"),
        )
    )
    client = TestClient(app)

    create_response = client.post("/api/v1/agent/sessions")
    assert create_response.status_code == 200
    session_id = create_response.json()["session_id"]

    message_response = client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={"content": "Please use A_DEMO file data to generate a scientific plot and report."},
    )
    assert message_response.status_code == 200
    payload = message_response.json()
    assert payload["session_id"] == session_id
    assert any(msg["message_type"] == "plan" for msg in payload["messages"])
    assert any(msg["message_type"] == "tool_call" for msg in payload["messages"])
    result_message = next(
        msg for msg in payload["messages"] if msg["role"] == "assistant" and msg["metadata"].get("task_id")
    )
    assert "scientific_plot" in result_message["content"]

    follow_up = client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={"content": "Show me the report again."},
    )
    assert follow_up.status_code == 200
    follow_up_payload = follow_up.json()
    assert len(follow_up_payload["messages"]) > len(payload["messages"])
    assert "business_code=A_DEMO" in follow_up_payload["messages"][-1]["content"]


def test_agent_session_artifact_proxy_reads_report(tmp_path: Path) -> None:
    app = build_api_app(
        Settings(
            artifact_base_dir=str(tmp_path / "artifacts"),
            sqlite_path=str(tmp_path / "artifacts" / "app.db"),
        )
    )
    client = TestClient(app)

    session_id = client.post("/api/v1/agent/sessions").json()["session_id"]
    payload = client.post(
        f"/api/v1/agent/sessions/{session_id}/messages",
        json={"content": "Please use A_DEMO file data to generate a scientific plot and report."},
    ).json()
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
    settings = Settings(
        artifact_base_dir=str(tmp_path / "artifacts"),
        sqlite_path=str(tmp_path / "artifacts" / "app.db"),
    )
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
