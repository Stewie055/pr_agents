from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MemoryService:
    """First-cut memory abstraction.

    Short-term memory is stored as case messages in SQLite. This class keeps a
    small in-process mid/long term facade so the Agent contract is explicit.
    """

    midterm_summaries: dict[str, str] = field(default_factory=dict)
    longterm_notes: list[str] = field(default_factory=list)

    def update_midterm(self, case_id: str, summary: str) -> None:
        self.midterm_summaries[case_id] = summary

    def retrieve(self, query: str) -> list[str]:
        tokens = {token.lower() for token in query.split() if len(token) > 2}
        if not tokens:
            return []
        return [note for note in self.longterm_notes if tokens & {token.lower() for token in note.split()}]
