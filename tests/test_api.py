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

    _, task_service = build_components(
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
