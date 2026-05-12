from __future__ import annotations

from semidiag.agent.memory import MemoryService
from semidiag.infrastructure.repository import SQLiteRepository


def test_midterm_memory_persists_in_repository(tmp_path):
    repository = SQLiteRepository(tmp_path / "test.sqlite3")
    case = repository.create_case("Memory case")
    memory = MemoryService(repository)

    memory.update_midterm(case.id, "first summary")
    memory.update_midterm(case.id, "updated summary")

    fresh = MemoryService(repository)
    assert fresh.get_midterm(case.id) == "updated summary"
    snapshot = repository.case_snapshot(case.id)
    assert len(snapshot["memory"]) == 1
    assert snapshot["memory"][0].content == "updated summary"
