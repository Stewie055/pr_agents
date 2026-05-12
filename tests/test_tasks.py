from __future__ import annotations

from fastapi.testclient import TestClient

from semidiag.api.main import AppState, create_app
from semidiag.infrastructure.tasks import InProcessTaskQueue


def test_in_process_task_queue_succeeds():
    queue = InProcessTaskQueue(max_workers=1)
    task = queue.submit(name="demo", payload={"value": 2}, handler=lambda payload: {"result": payload["value"] + 1})

    completed = queue.wait(task.id, timeout=2)

    assert completed is not None
    assert completed.status == "succeeded"
    assert completed.result == {"result": 3}


def test_in_process_task_queue_records_failure():
    queue = InProcessTaskQueue(max_workers=1)

    def fail(payload):
        raise RuntimeError(f"bad payload: {payload['value']}")

    task = queue.submit(name="failure", payload={"value": "x"}, handler=fail)
    completed = queue.wait(task.id, timeout=2)

    assert completed is not None
    assert completed.status == "failed"
    assert completed.error == "bad payload: x"


def test_task_status_api_returns_queue_snapshot(tmp_path):
    state = AppState(tmp_path)
    task = state.task_queue.submit(name="demo", payload={"value": 2}, handler=lambda payload: {"result": payload["value"] + 1})
    completed = state.task_queue.wait(task.id, timeout=2)
    assert completed is not None
    app = create_app(state)
    client = TestClient(app)

    listed = client.get("/api/tasks")
    fetched = client.get(f"/api/tasks/{task.id}")

    assert listed.status_code == 200
    assert listed.json()["tasks"][0]["id"] == task.id
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "succeeded"
