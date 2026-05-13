from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def utc_now() -> datetime:
    return datetime.now(UTC)


ArtifactKind = Literal[
    "dataset",
    "table",
    "chart",
    "model_result",
    "diagnosis",
    "report",
    "file",
]


class DatasetRecord(BaseModel):
    id: str = Field(default_factory=lambda: new_id("ds"))
    case_id: str
    filename: str
    path: str
    content_type: str | None = None
    log_kind: Literal["LT-D", "LT-C", "LT-R"] | None = None
    scenario: Literal["offline_setup", "online_production"] | None = None
    model_variant: str | None = None
    matched_rule: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class DiagnosticCase(BaseModel):
    id: str = Field(default_factory=lambda: new_id("case"))
    title: str
    equipment_type: str = "generic_semiconductor_tool"
    status: Literal["open", "analyzing", "awaiting_review", "closed"] = "open"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class AgentMessage(BaseModel):
    id: str = Field(default_factory=lambda: new_id("msg"))
    case_id: str
    role: Literal["user", "assistant", "system", "tool"]
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class MemoryRecord(BaseModel):
    id: str = Field(default_factory=lambda: new_id("mem"))
    case_id: str
    scope: Literal["midterm", "longterm"]
    content: str
    updated_at: datetime = Field(default_factory=utc_now)


class KnowledgeRecord(BaseModel):
    id: str = Field(default_factory=lambda: new_id("kn"))
    title: str
    content: str
    source: str = "local"
    created_at: datetime = Field(default_factory=utc_now)


class WorkflowTemplate(BaseModel):
    id: str = Field(default_factory=lambda: new_id("wf"))
    name: str
    description: str = ""
    steps: list[dict[str, Any]] = Field(default_factory=list)
    source_case_id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class Evidence(BaseModel):
    id: str = Field(default_factory=lambda: new_id("ev"))
    case_id: str
    title: str
    evidence_type: Literal["metric", "chart", "rule", "model", "knowledge", "case_history"]
    summary: str
    data: dict[str, Any] = Field(default_factory=dict)
    source_artifact_id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class DiagnosisConclusion(BaseModel):
    id: str = Field(default_factory=lambda: new_id("diag"))
    case_id: str
    title: str
    possible_causes: list[str]
    confidence: float = Field(ge=0.0, le=1.0)
    risk_level: Literal["low", "medium", "high"]
    recommendations: list[str]
    evidence_ids: list[str] = Field(default_factory=list)
    human_review_status: Literal["draft", "approved", "rejected"] = "draft"
    created_at: datetime = Field(default_factory=utc_now)


class AnalysisArtifact(BaseModel):
    id: str = Field(default_factory=lambda: new_id("art"))
    case_id: str
    kind: ArtifactKind
    title: str
    summary: str
    data: dict[str, Any] = Field(default_factory=dict)
    source_file_id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class ToolCallTrace(BaseModel):
    id: str = Field(default_factory=lambda: new_id("tool"))
    case_id: str
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    status: Literal["success", "error", "approval_required"]
    result_summary: str = ""
    error: str | None = None
    duration_ms: int = 0
    created_at: datetime = Field(default_factory=utc_now)


class AgentStepTrace(BaseModel):
    id: str = Field(default_factory=lambda: new_id("step"))
    case_id: str
    step_index: int
    phase: Literal["route", "gate", "reason", "act", "observe", "finalize", "stop"]
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    observations: list[dict[str, Any]] = Field(default_factory=list)
    llm_metadata: dict[str, Any] = Field(default_factory=dict)
    stop_reason: str | None = None
    duration_ms: int = 0
    created_at: datetime = Field(default_factory=utc_now)


class AuditEvent(BaseModel):
    id: str = Field(default_factory=lambda: new_id("audit"))
    case_id: str
    actor: str
    action: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class LLMAuditEvent(BaseModel):
    id: str = Field(default_factory=lambda: new_id("llm"))
    case_id: str
    provider: str
    model: str
    request: dict[str, Any] = Field(default_factory=dict)
    response: dict[str, Any] | None = None
    error: str | None = None
    duration_ms: int = 0
    created_at: datetime = Field(default_factory=utc_now)


class TaskRecord(BaseModel):
    id: str = Field(default_factory=lambda: new_id("task"))
    case_id: str | None = None
    name: str
    status: Literal["pending", "running", "succeeded", "failed", "cancelled", "interrupted"] = "pending"
    payload: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] | None = None
    error: str | None = None
    artifact_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    created_by: str = "system"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    started_at: datetime | None = None
    finished_at: datetime | None = None
