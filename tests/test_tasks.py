from __future__ import annotations

from fastapi.testclient import TestClient

from semidiag.api.main import AppState, create_app
from semidiag.domain import TaskRecord
from semidiag.infrastructure.repository import SQLiteRepository
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
    assert fetched.json()["case_id"] is None


def test_task_cancel_api_returns_task_snapshot(tmp_path):
    state = AppState(tmp_path)
    task = state.task_queue.submit(name="demo", payload={"value": 2}, handler=lambda payload: {"result": payload["value"] + 1})
    app = create_app(state)
    client = TestClient(app)

    response = client.post(f"/api/tasks/{task.id}/cancel")

    assert response.status_code == 200
    assert response.json()["id"] == task.id


def test_task_queue_persists_records_and_result_artifacts(tmp_path):
    repository = SQLiteRepository(tmp_path / "tasks.sqlite3")
    queue = InProcessTaskQueue(max_workers=1, repository=repository)
    case = repository.create_case("Task persistence")

    task = queue.submit(
        name="demo",
        case_id=case.id,
        created_by="engineer",
        payload={"value": 2},
        handler=lambda payload: {"result": payload["value"] + 1, "artifact_ids": ["art_1"]},
    )
    completed = queue.wait(task.id, timeout=2)
    persisted = repository.get_task(task.id)

    assert completed is not None
    assert completed.status == "succeeded"
    assert completed.case_id == case.id
    assert completed.created_by == "engineer"
    assert completed.artifact_ids == ["art_1"]
    assert persisted is not None
    assert persisted.result == {"result": 3, "artifact_ids": ["art_1"]}


def test_task_queue_marks_unfinished_persisted_tasks_interrupted(tmp_path):
    repository = SQLiteRepository(tmp_path / "tasks.sqlite3")
    case = repository.create_case("Interrupted task")
    repository.upsert_task(TaskRecord(case_id=case.id, name="stale", status="running"))

    queue = InProcessTaskQueue(max_workers=1, repository=repository)
    tasks = queue.list_tasks(case_id=case.id)

    assert tasks[0].status == "interrupted"
    assert "restarted" in (tasks[0].error or "")


def test_task_status_api_filters_by_case_id(tmp_path):
    state = AppState(tmp_path)
    first_case = state.repository.create_case("First")
    second_case = state.repository.create_case("Second")
    first = state.task_queue.submit(
        name="first",
        case_id=first_case.id,
        payload={},
        handler=lambda payload: {"artifact_ids": ["art_first"]},
    )
    second = state.task_queue.submit(
        name="second",
        case_id=second_case.id,
        payload={},
        handler=lambda payload: {"artifact_ids": ["art_second"]},
    )
    state.task_queue.wait(first.id, timeout=2)
    state.task_queue.wait(second.id, timeout=2)
    app = create_app(state)
    client = TestClient(app)

    response = client.get(f"/api/tasks?case_id={first_case.id}")
    snapshot = client.get(f"/api/cases/{first_case.id}")

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["tasks"]] == [first.id]
    assert [item["id"] for item in snapshot.json()["tasks"]] == [first.id]
