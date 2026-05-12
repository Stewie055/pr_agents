from __future__ import annotations

from fastapi.testclient import TestClient

from semidiag.agent.memory import MemoryService
from semidiag.api.main import AppState, create_app
from semidiag.domain import KnowledgeRecord
from semidiag.infrastructure.repository import SQLiteRepository


def test_repository_searches_local_knowledge(tmp_path):
    repository = SQLiteRepository(tmp_path / "test.sqlite3")
    repository.add_knowledge(
        KnowledgeRecord(
            title="Chamber temperature drift",
            content="Temperature drift can indicate cooling loop instability.",
            source="runbook",
        )
    )
    repository.add_knowledge(KnowledgeRecord(title="Pressure guide", content="Pressure readings.", source="manual"))

    results = repository.search_knowledge("temperature cooling")

    assert [item.title for item in results] == ["Chamber temperature drift"]
    assert MemoryService(repository).retrieve("cooling")[0].startswith("Chamber temperature drift (runbook)")


def test_knowledge_api_creates_and_searches_records(tmp_path):
    state = AppState(tmp_path)
    app = create_app(state)
    client = TestClient(app)

    created = client.post(
        "/api/knowledge",
        json={
            "title": "RF power instability",
            "content": "RF power instability can reduce throughput.",
            "source": "local-note",
        },
    )
    searched = client.get("/api/knowledge?q=throughput")

    assert created.status_code == 200
    assert created.json()["title"] == "RF power instability"
    assert searched.status_code == 200
    assert searched.json()["knowledge"][0]["source"] == "local-note"
