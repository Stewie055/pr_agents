from __future__ import annotations

from dataclasses import dataclass, field

from semidiag.domain import MemoryRecord
from semidiag.infrastructure.repository import SQLiteRepository


@dataclass
class MemoryService:
    """First-cut memory abstraction.

    Short-term memory is stored as case messages in SQLite. This class keeps a
    small in-process mid/long term facade so the Agent contract is explicit.
    """

    repository: SQLiteRepository | None = None
    midterm_summaries: dict[str, str] = field(default_factory=dict)
    longterm_notes: list[str] = field(default_factory=list)

    def update_midterm(self, case_id: str, summary: str) -> None:
        self.midterm_summaries[case_id] = summary
        if self.repository is not None:
            self.repository.upsert_memory(MemoryRecord(case_id=case_id, scope="midterm", content=summary))

    def get_midterm(self, case_id: str) -> str | None:
        if case_id in self.midterm_summaries:
            return self.midterm_summaries[case_id]
        if self.repository is None:
            return None
        memory = self.repository.get_case_memory(case_id, "midterm")
        if memory is None:
            return None
        self.midterm_summaries[case_id] = memory.content
        return memory.content

    def retrieve(self, query: str) -> list[str]:
        tokens = {token.lower() for token in query.split() if len(token) > 2}
        if not tokens:
            return []
        return [note for note in self.longterm_notes if tokens & {token.lower() for token in note.split()}]
