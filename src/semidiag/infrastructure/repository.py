from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable, TypeVar

from pydantic import BaseModel

from semidiag.domain import (
    AgentMessage,
    AgentStepTrace,
    AnalysisArtifact,
    AuditEvent,
    DatasetRecord,
    DiagnosticCase,
    Evidence,
    LLMAuditEvent,
    ToolCallTrace,
)

ModelT = TypeVar("ModelT", bound=BaseModel)


class SQLiteRepository:
    """Small repository for the first platform slice.

    The schema stores JSON payloads so the domain model can evolve while the
    public interfaces settle. Production migration can split these into typed
    SQLAlchemy tables without changing the service contracts.
    """

    def __init__(self, db_path: Path | str = "var/semidiag.sqlite3") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                create table if not exists records (
                    bucket text not null,
                    id text not null,
                    payload text not null,
                    created_at text not null,
                    primary key (bucket, id)
                );
                create index if not exists idx_records_bucket_created
                on records(bucket, created_at);
                """
            )

    def _put(self, bucket: str, model: BaseModel) -> None:
        payload = model.model_dump(mode="json")
        created_at = str(payload.get("created_at") or payload.get("updated_at") or "")
        with self._connect() as conn:
            conn.execute(
                """
                insert or replace into records(bucket, id, payload, created_at)
                values (?, ?, ?, ?)
                """,
                (bucket, payload["id"], json.dumps(payload, ensure_ascii=False), created_at),
            )

    def _get(self, bucket: str, record_id: str, model_type: type[ModelT]) -> ModelT | None:
        with self._connect() as conn:
            row = conn.execute(
                "select payload from records where bucket = ? and id = ?",
                (bucket, record_id),
            ).fetchone()
        if row is None:
            return None
        return model_type.model_validate(json.loads(row["payload"]))

    def _list(self, bucket: str, model_type: type[ModelT]) -> list[ModelT]:
        with self._connect() as conn:
            rows = conn.execute(
                "select payload from records where bucket = ? order by created_at asc",
                (bucket,),
            ).fetchall()
        return [model_type.model_validate(json.loads(row["payload"])) for row in rows]

    def create_case(self, title: str, equipment_type: str = "generic_semiconductor_tool") -> DiagnosticCase:
        case = DiagnosticCase(title=title, equipment_type=equipment_type)
        self._put("case", case)
        self.add_audit_event(
            AuditEvent(case_id=case.id, actor="system", action="case.created", details={"title": title})
        )
        return case

    def get_case(self, case_id: str) -> DiagnosticCase | None:
        return self._get("case", case_id, DiagnosticCase)

    def list_cases(self) -> list[DiagnosticCase]:
        return self._list("case", DiagnosticCase)

    def add_dataset(self, dataset: DatasetRecord) -> DatasetRecord:
        self._put("dataset", dataset)
        return dataset

    def get_dataset(self, dataset_id: str) -> DatasetRecord | None:
        return self._get("dataset", dataset_id, DatasetRecord)

    def list_case_datasets(self, case_id: str) -> list[DatasetRecord]:
        return [item for item in self._list("dataset", DatasetRecord) if item.case_id == case_id]

    def add_message(self, message: AgentMessage) -> AgentMessage:
        self._put("message", message)
        return message

    def list_case_messages(self, case_id: str) -> list[AgentMessage]:
        return [item for item in self._list("message", AgentMessage) if item.case_id == case_id]

    def add_artifact(self, artifact: AnalysisArtifact) -> AnalysisArtifact:
        self._put("artifact", artifact)
        return artifact

    def list_case_artifacts(self, case_id: str) -> list[AnalysisArtifact]:
        return [item for item in self._list("artifact", AnalysisArtifact) if item.case_id == case_id]

    def add_evidence(self, evidence: Evidence) -> Evidence:
        self._put("evidence", evidence)
        return evidence

    def list_case_evidence(self, case_id: str) -> list[Evidence]:
        return [item for item in self._list("evidence", Evidence) if item.case_id == case_id]

    def add_tool_trace(self, trace: ToolCallTrace) -> ToolCallTrace:
        self._put("tool_trace", trace)
        return trace

    def list_case_tool_traces(self, case_id: str) -> list[ToolCallTrace]:
        return [item for item in self._list("tool_trace", ToolCallTrace) if item.case_id == case_id]

    def add_agent_step_trace(self, trace: AgentStepTrace) -> AgentStepTrace:
        self._put("agent_step", trace)
        return trace

    def list_case_agent_step_traces(self, case_id: str) -> list[AgentStepTrace]:
        return [item for item in self._list("agent_step", AgentStepTrace) if item.case_id == case_id]

    def add_audit_event(self, event: AuditEvent) -> AuditEvent:
        self._put("audit", event)
        return event

    def list_case_audit_events(self, case_id: str) -> list[AuditEvent]:
        return [item for item in self._list("audit", AuditEvent) if item.case_id == case_id]

    def add_llm_audit_event(self, event: LLMAuditEvent) -> LLMAuditEvent:
        self._put("llm_audit", event)
        return event

    def list_case_llm_audit_events(self, case_id: str) -> list[LLMAuditEvent]:
        return [item for item in self._list("llm_audit", LLMAuditEvent) if item.case_id == case_id]

    def case_snapshot(self, case_id: str) -> dict[str, Any]:
        case = self.get_case(case_id)
        if case is None:
            raise KeyError(case_id)
        return {
            "case": case,
            "datasets": self.list_case_datasets(case_id),
            "messages": self.list_case_messages(case_id),
            "artifacts": self.list_case_artifacts(case_id),
            "evidence": self.list_case_evidence(case_id),
            "tool_traces": self.list_case_tool_traces(case_id),
            "agent_steps": self.list_case_agent_step_traces(case_id),
            "audit_events": self.list_case_audit_events(case_id),
            "llm_audit_events": self.list_case_llm_audit_events(case_id),
        }
