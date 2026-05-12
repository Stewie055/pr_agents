from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any

from pydantic import BaseModel, Field

from semidiag.domain import AnalysisArtifact, AuditEvent, Evidence, ToolCallTrace
from semidiag.infrastructure.metrics import MetricPoint, MetricRepository
from semidiag.infrastructure.repository import SQLiteRepository
from semidiag.plugins import DiagnosticPlugin


class ToolDefinition(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    required_permissions: list[str] = Field(default_factory=list)
    risk_level: str = "low"

    def as_openai_tool(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema or {"type": "object", "properties": {}},
            },
        }


@dataclass
class ToolContext:
    case_id: str
    actor: str
    repository: SQLiteRepository
    plugin: DiagnosticPlugin
    metric_repository: MetricRepository | None = None


@dataclass
class ToolObservation:
    tool_name: str
    summary: str
    data: dict[str, Any] = field(default_factory=dict)
    artifact_ids: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    next_suggestions: list[str] = field(default_factory=list)


@dataclass
class ToolResult:
    summary: str
    artifacts: list[AnalysisArtifact] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)
    observation: ToolObservation | None = None


ToolHandler = Callable[[ToolContext, dict[str, Any]], ToolResult]


class ToolRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, ToolDefinition] = {}
        self._handlers: dict[str, ToolHandler] = {}

    def register(self, definition: ToolDefinition, handler: ToolHandler) -> None:
        self._definitions[definition.name] = definition
        self._handlers[definition.name] = handler

    def list_tools(self) -> list[ToolDefinition]:
        return list(self._definitions.values())

    def get_tool(self, name: str) -> ToolDefinition | None:
        return self._definitions.get(name)

    def openai_tools(self) -> list[dict[str, Any]]:
        return [definition.as_openai_tool() for definition in self.list_tools()]

    def prompt_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": definition.name,
                "description": definition.description,
                "input_schema": definition.input_schema or {"type": "object", "properties": {}},
                "output_schema": definition.output_schema or {"type": "object", "properties": {}},
                "risk_level": definition.risk_level,
                "usage_hint": definition.description,
            }
            for definition in self.list_tools()
        ]

    def run(self, name: str, context: ToolContext, arguments: dict[str, Any]) -> ToolResult:
        if name not in self._handlers:
            raise KeyError(f"Tool not registered: {name}")
        definition = self._definitions[name]
        if definition.risk_level == "high":
            trace = ToolCallTrace(
                case_id=context.case_id,
                tool_name=name,
                arguments=arguments,
                status="approval_required",
                result_summary="Human approval is required before running this tool.",
            )
            context.repository.add_tool_trace(trace)
            raise PermissionError(trace.result_summary)

        started = perf_counter()
        try:
            result = self._handlers[name](context, arguments)
        except Exception as exc:
            duration = int((perf_counter() - started) * 1000)
            context.repository.add_tool_trace(
                ToolCallTrace(
                    case_id=context.case_id,
                    tool_name=name,
                    arguments=arguments,
                    status="error",
                    error=str(exc),
                    duration_ms=duration,
                )
            )
            raise

        for artifact in result.artifacts:
            context.repository.add_artifact(artifact)
        for evidence in result.evidence:
            context.repository.add_evidence(evidence)

        duration = int((perf_counter() - started) * 1000)
        context.repository.add_tool_trace(
            ToolCallTrace(
                case_id=context.case_id,
                tool_name=name,
                arguments=arguments,
                status="success",
                result_summary=result.summary,
                duration_ms=duration,
            )
        )
        context.repository.add_audit_event(
            AuditEvent(
                case_id=context.case_id,
                actor=context.actor,
                action="tool.executed",
                details={"tool": name, "arguments": arguments, "risk_level": definition.risk_level},
            )
        )
        return result


def build_default_registry() -> ToolRegistry:
    registry = ToolRegistry()

    registry.register(
        ToolDefinition(
            name="parse_dataset",
            description=(
                "Parse an uploaded equipment performance CSV file and create a dataset artifact. "
                "Use this before profiling or diagnosis if the dataset has not been parsed."
            ),
            input_schema={
                "type": "object",
                "properties": {"dataset_id": {"type": "string", "description": "Dataset id uploaded to the current case."}},
                "required": ["dataset_id"],
                "additionalProperties": False,
            },
            output_schema={"type": "object", "properties": {"artifact": {"type": "string", "const": "dataset"}}},
        ),
        _parse_dataset,
    )
    registry.register(
        ToolDefinition(
            name="inspect_dataset",
            description=(
                "Inspect dataset schema, column names, column types, row count, and a small preview. "
                "Use this when you need to understand fields or sample rows before analysis."
            ),
            input_schema={
                "type": "object",
                "properties": {"dataset_id": {"type": "string", "description": "Dataset id uploaded to the current case."}},
                "required": ["dataset_id"],
                "additionalProperties": False,
            },
            output_schema={"type": "object", "properties": {"artifact": {"type": "string", "const": "table"}}},
        ),
        _inspect_dataset,
    )
    registry.register(
        ToolDefinition(
            name="profile_dataset",
            description=(
                "Profile numeric equipment metrics and collect evidence such as variance and outlier signals. "
                "Use this after parsing or inspecting the dataset."
            ),
            input_schema={
                "type": "object",
                "properties": {"dataset_id": {"type": "string", "description": "Dataset id uploaded to the current case."}},
                "required": ["dataset_id"],
                "additionalProperties": False,
            },
            output_schema={"type": "object", "properties": {"artifact": {"type": "string", "const": "table"}}},
        ),
        _profile_dataset,
    )
    registry.register(
        ToolDefinition(
            name="build_trend_chart",
            description="Generate Matplotlib PNG trend charts for numeric equipment metrics when the user needs visual analysis.",
            input_schema={
                "type": "object",
                "properties": {"dataset_id": {"type": "string", "description": "Dataset id uploaded to the current case."}},
                "required": ["dataset_id"],
                "additionalProperties": False,
            },
            output_schema={"type": "object", "properties": {"artifact": {"type": "string", "const": "chart"}}},
        ),
        _build_trend_chart,
    )
    registry.register(
        ToolDefinition(
            name="diagnose_performance",
            description=(
                "Generate a preliminary equipment performance diagnosis from existing profile artifacts and evidence. "
                "Use this after profile_dataset has produced metric evidence."
            ),
            input_schema={"type": "object", "properties": {}, "additionalProperties": False},
            output_schema={"type": "object", "properties": {"artifact": {"type": "string", "const": "diagnosis"}}},
        ),
        _diagnose_performance,
    )
    registry.register(
        ToolDefinition(
            name="generate_report",
            description="Generate an editable diagnostic report draft after analysis or diagnosis artifacts are available.",
            input_schema={"type": "object", "properties": {}, "additionalProperties": False},
            output_schema={"type": "object", "properties": {"artifact": {"type": "string", "const": "report"}}},
        ),
        _generate_report,
    )
    return registry


def _dataset(context: ToolContext, dataset_id: str):
    dataset = context.repository.get_dataset(dataset_id)
    if dataset is None or dataset.case_id != context.case_id:
        raise ValueError(f"Dataset not found for case: {dataset_id}")
    return dataset


def _parse_dataset(context: ToolContext, arguments: dict[str, Any]) -> ToolResult:
    dataset = _dataset(context, arguments["dataset_id"])
    artifact = context.plugin.diagnostic_service().parse_dataset(
        case_id=context.case_id,
        dataset_id=dataset.id,
        path=dataset.path,
    )
    metric_point_count = 0
    if context.metric_repository is not None:
        points = [
            MetricPoint(
                case_id=context.case_id,
                dataset_id=dataset.id,
                metric_name=item["metric_name"],
                sample_index=item["sample_index"],
                value=item["value"],
            )
            for item in context.plugin.diagnostic_service().extract_metric_points(
                case_id=context.case_id,
                dataset_id=dataset.id,
                path=dataset.path,
            )
        ]
        metric_point_count = context.metric_repository.replace_dataset_points(dataset.id, points)
    return ToolResult(
        summary=f"{artifact.summary} Stored {metric_point_count} metric point(s)."
        if context.metric_repository is not None
        else artifact.summary,
        artifacts=[artifact],
        payload={"artifact_id": artifact.id, "metric_point_count": metric_point_count},
        observation=ToolObservation(
            tool_name="parse_dataset",
            summary=artifact.summary,
            data={
                "columns": artifact.data.get("columns", []),
                "row_count": artifact.data.get("row_count", 0),
                "preview": artifact.data.get("rows", [])[:5],
                "metric_point_count": metric_point_count,
            },
            artifact_ids=[artifact.id],
            next_suggestions=["inspect_dataset", "profile_dataset"],
        ),
    )


def _inspect_dataset(context: ToolContext, arguments: dict[str, Any]) -> ToolResult:
    dataset = _dataset(context, arguments["dataset_id"])
    artifact = context.plugin.diagnostic_service().inspect_dataset(
        case_id=context.case_id,
        dataset_id=dataset.id,
        path=dataset.path,
    )
    return ToolResult(
        summary=artifact.summary,
        artifacts=[artifact],
        payload={"artifact_id": artifact.id},
        observation=ToolObservation(
            tool_name="inspect_dataset",
            summary=artifact.summary,
            data={
                "columns": artifact.data.get("columns", []),
                "column_types": artifact.data.get("column_types", {}),
                "numeric_columns": artifact.data.get("numeric_columns", []),
                "row_count": artifact.data.get("row_count", 0),
                "preview": artifact.data.get("preview", []),
            },
            artifact_ids=[artifact.id],
            next_suggestions=["profile_dataset", "build_trend_chart"],
        ),
    )


def _profile_dataset(context: ToolContext, arguments: dict[str, Any]) -> ToolResult:
    dataset = _dataset(context, arguments["dataset_id"])
    artifact, evidence = context.plugin.diagnostic_service().profile_dataset(
        case_id=context.case_id,
        dataset_id=dataset.id,
        path=dataset.path,
    )
    return ToolResult(
        summary=artifact.summary,
        artifacts=[artifact],
        evidence=evidence,
        payload={"artifact_id": artifact.id},
        observation=ToolObservation(
            tool_name="profile_dataset",
            summary=artifact.summary,
            data={
                "profile": artifact.data.get("profile", {}),
                "evidence": [{"id": item.id, "title": item.title, "summary": item.summary} for item in evidence],
            },
            artifact_ids=[artifact.id],
            evidence_ids=[item.id for item in evidence],
            next_suggestions=["build_trend_chart", "diagnose_performance"],
        ),
    )


def _build_trend_chart(context: ToolContext, arguments: dict[str, Any]) -> ToolResult:
    dataset = _dataset(context, arguments["dataset_id"])
    artifacts = context.plugin.diagnostic_service().build_chart(
        case_id=context.case_id,
        dataset_id=dataset.id,
        path=dataset.path,
    )
    chart_artifacts = [artifact for artifact in artifacts if artifact.kind == "chart"]
    image_charts = [artifact for artifact in chart_artifacts if artifact.data.get("render_type") == "image"]
    summary = f"Generated {len(image_charts)} Matplotlib chart file(s)." if image_charts else artifacts[0].summary
    return ToolResult(
        summary=summary,
        artifacts=artifacts,
        payload={"artifact_ids": [artifact.id for artifact in artifacts]},
        observation=ToolObservation(
            tool_name="build_trend_chart",
            summary=summary,
            data={
                "render_type": "image" if image_charts else "none",
                "chart_count": len(image_charts),
                "charts": [
                    {
                        "title": artifact.title,
                        "figure_kind": artifact.data.get("figure_kind"),
                        "display_group": artifact.data.get("display_group"),
                        "series_names": artifact.data.get("series_names", []),
                        "point_count": artifact.data.get("point_count", 0),
                        "mime_type": artifact.data.get("mime_type"),
                    }
                    for artifact in image_charts
                ],
            },
            artifact_ids=[artifact.id for artifact in artifacts],
            next_suggestions=["diagnose_performance"],
        ),
    )


def _diagnose_performance(context: ToolContext, arguments: dict[str, Any]) -> ToolResult:
    artifacts = context.repository.list_case_artifacts(context.case_id)
    profile = next((item for item in reversed(artifacts) if item.kind == "table"), None)
    if profile is None:
        raise ValueError("profile_dataset must run before diagnose_performance")
    evidence = context.repository.list_case_evidence(context.case_id)
    artifact, conclusion = context.plugin.diagnostic_service().diagnose(
        case_id=context.case_id,
        profile_artifact=profile,
        evidence=evidence,
    )
    return ToolResult(
        summary=artifact.summary,
        artifacts=[artifact],
        payload={"conclusion": conclusion.model_dump(mode="json")},
        observation=ToolObservation(
            tool_name="diagnose_performance",
            summary=artifact.summary,
            data={
                "title": conclusion.title,
                "possible_causes": conclusion.possible_causes,
                "confidence": conclusion.confidence,
                "risk_level": conclusion.risk_level,
                "recommendations": conclusion.recommendations,
                "evidence_ids": conclusion.evidence_ids,
            },
            artifact_ids=[artifact.id],
            evidence_ids=conclusion.evidence_ids,
            next_suggestions=["generate_report"],
        ),
    )


def _generate_report(context: ToolContext, arguments: dict[str, Any]) -> ToolResult:
    artifacts = context.repository.list_case_artifacts(context.case_id)
    evidence = context.repository.list_case_evidence(context.case_id)
    artifact = context.plugin.diagnostic_service().generate_report(
        case_id=context.case_id,
        artifacts=artifacts,
        evidence=evidence,
    )
    return ToolResult(
        summary=artifact.summary,
        artifacts=[artifact],
        payload={"artifact_id": artifact.id},
        observation=ToolObservation(
            tool_name="generate_report",
            summary=artifact.summary,
            data={
                "sections": [section.get("heading") for section in artifact.data.get("sections", [])],
                "format": artifact.data.get("format"),
                "mime_type": artifact.data.get("mime_type"),
                "chart_count": artifact.data.get("chart_count", 0),
                "template_engine": artifact.data.get("template_engine"),
            },
            artifact_ids=[artifact.id],
        ),
    )
