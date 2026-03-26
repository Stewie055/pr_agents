from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class DataSourceType(str, Enum):
    FILE = "file"
    DATABASE = "database"


class ArtifactType(str, Enum):
    DATASET = "dataset"
    CHART = "chart"
    REPORT = "report"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class TaskContext(BaseModel):
    session_id: str = Field(default_factory=lambda: f"session-{uuid4().hex[:8]}")
    task_id: str = Field(default_factory=lambda: f"task-{uuid4().hex[:8]}")
    user_request: str
    workspace: str = "artifacts"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def workspace_path(self) -> Path:
        return Path(self.workspace)


class ArtifactRef(BaseModel):
    artifact_id: str
    artifact_type: ArtifactType
    uri: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class DatasetRef(BaseModel):
    dataset_id: str
    source_type: DataSourceType
    source_uri: str
    columns: list[str] = Field(default_factory=list)
    row_count: int = 0
    artifact: ArtifactRef | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AnalysisRequest(BaseModel):
    objective: str
    dataset_id: str | None = None
    operations: list[str] = Field(default_factory=list)
    output_formats: list[str] = Field(default_factory=lambda: ["png", "md"])
    parameters: dict[str, Any] = Field(default_factory=dict)


class MetricResult(BaseModel):
    name: str
    value: float | int | str
    unit: str | None = None


class AnalysisResult(BaseModel):
    summary: str
    metrics: list[MetricResult] = Field(default_factory=list)
    insights: list[str] = Field(default_factory=list)
    dataset_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChartArtifact(BaseModel):
    chart_id: str
    title: str
    chart_type: str
    artifact: ArtifactRef
    config: dict[str, Any] = Field(default_factory=dict)


class ReportArtifact(BaseModel):
    report_id: str
    title: str
    artifact: ArtifactRef
    sections: list[str] = Field(default_factory=list)
    summary: str


class WorkflowError(BaseModel):
    code: str
    message: str
    step: str
    details: dict[str, Any] = Field(default_factory=dict)


class WorkflowResult(BaseModel):
    context: TaskContext
    dataset: DatasetRef | None = None
    analysis: AnalysisResult | None = None
    chart: ChartArtifact | None = None
    report: ReportArtifact | None = None
    artifacts: list[ArtifactRef] = Field(default_factory=list)
    errors: list[WorkflowError] = Field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


class SessionRecord(BaseModel):
    session_id: str
    created_at: str
    updated_at: str


class TaskRecord(BaseModel):
    task_id: str
    session_id: str
    task_type: str
    status: TaskStatus
    objective: str
    input_summary: dict[str, Any] = Field(default_factory=dict)
    result_summary: dict[str, Any] = Field(default_factory=dict)
    error_summary: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str
    completed_at: str | None = None


class ArtifactRecord(BaseModel):
    artifact_id: str
    task_id: str
    artifact_type: ArtifactType
    uri: str
    filename: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class FileAnalysisInput(BaseModel):
    file_name: str
    content: str
    objective: str
    operations: list[str] = Field(default_factory=lambda: ["clean", "analyze", "visualize", "report"])


class DatabaseAnalysisInput(BaseModel):
    query_name: str
    objective: str
    sql: str
    operations: list[str] = Field(default_factory=lambda: ["clean", "analyze", "visualize", "report"])


class ReportGenerationInput(BaseModel):
    objective: str
    dataset: DatasetRef | None = None
    analysis: AnalysisResult
    chart: ChartArtifact | None = None


class FileAnalysisRequest(BaseModel):
    objective: str
    file_name: str
    content: str
    operations: list[str] = Field(default_factory=lambda: ["clean", "analyze", "visualize", "report"])
    session_id: str | None = None


class DatabaseAnalysisRequest(BaseModel):
    objective: str
    query_name: str
    sql: str
    operations: list[str] = Field(default_factory=lambda: ["clean", "analyze", "visualize", "report"])
    session_id: str | None = None


class TaskResponse(BaseModel):
    task_id: str
    session_id: str
    status: TaskStatus
    result: WorkflowResult | None = None
    error: WorkflowError | None = None


class TaskDetailResponse(BaseModel):
    task: TaskRecord
    artifacts: list[ArtifactRecord] = Field(default_factory=list)
    result: WorkflowResult | None = None


class SessionTasksResponse(BaseModel):
    session_id: str
    tasks: list[TaskRecord] = Field(default_factory=list)
