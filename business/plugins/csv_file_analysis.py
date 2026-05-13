from __future__ import annotations

from typing import Any

from business.services.csv_file_analysis import CSVDiagnosticService
from semidiag.infrastructure.metrics import MetricPoint
from semidiag.plugins import CalibrationPlugin, CalibrationPluginManifest
from semidiag.tools import ToolContext, ToolDefinition, ToolResult, ToolSpec


def register(registry):
    tools = [
        ToolSpec(
            definition=ToolDefinition(
                name="parse_dataset",
                description=(
                    "Parse the current CSV file and create a dataset artifact. "
                    "Use this before profiling or diagnosis if the current CSV has not been parsed."
                ),
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                output_schema={"type": "object", "properties": {"artifact": {"type": "string", "const": "dataset"}}},
                origin="business:csv.file_analysis",
                phase="parse",
                capability_tags=["csv", "dataset"],
                recovery_suggestions=["inspect_dataset"],
            ),
            handler=parse_dataset,
        ),
        ToolSpec(
            definition=ToolDefinition(
                name="inspect_dataset",
                description=(
                    "Inspect current CSV schema, column names, column types, row count, and a small preview. "
                    "Use this when fields or sample rows are needed before analysis."
                ),
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                output_schema={"type": "object", "properties": {"artifact": {"type": "string", "const": "table"}}},
                origin="business:csv.file_analysis",
                phase="parse",
                capability_tags=["csv", "schema"],
                recovery_suggestions=["parse_dataset"],
            ),
            handler=inspect_dataset,
        ),
        ToolSpec(
            definition=ToolDefinition(
                name="profile_dataset",
                description=(
                    "Profile numeric CSV metrics and collect evidence such as variance and outlier signals. "
                    "Use this after parsing or inspecting the current CSV."
                ),
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                output_schema={"type": "object", "properties": {"artifact": {"type": "string", "const": "table"}}},
                origin="business:csv.file_analysis",
                phase="analyze",
                capability_tags=["csv", "profile"],
                recovery_suggestions=["inspect_dataset", "parse_dataset"],
            ),
            handler=profile_dataset,
        ),
        ToolSpec(
            definition=ToolDefinition(
                name="build_trend_chart",
                description="Generate Matplotlib PNG trend charts for current numeric CSV columns when visual analysis is needed.",
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                output_schema={"type": "object", "properties": {"artifact": {"type": "string", "const": "chart"}}},
                origin="business:csv.file_analysis",
                phase="plot",
                capability_tags=["csv", "chart", "matplotlib"],
                recovery_suggestions=["inspect_dataset", "profile_dataset"],
            ),
            handler=build_trend_chart,
        ),
        ToolSpec(
            definition=ToolDefinition(
                name="diagnose_performance",
                description=(
                    "Generate a preliminary performance diagnosis from existing CSV profile artifacts and evidence. "
                    "Use this after profile_dataset has produced metric evidence."
                ),
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                output_schema={"type": "object", "properties": {"artifact": {"type": "string", "const": "diagnosis"}}},
                origin="business:csv.file_analysis",
                phase="diagnose",
                capability_tags=["diagnosis", "csv"],
                recovery_suggestions=["profile_dataset", "build_trend_chart"],
            ),
            handler=diagnose_performance,
        ),
        ToolSpec(
            definition=ToolDefinition(
                name="generate_report",
                description="Generate an editable PPTX diagnostic report draft after CSV analysis or diagnosis artifacts are available.",
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                output_schema={"type": "object", "properties": {"artifact": {"type": "string", "const": "report"}}},
                origin="business:csv.file_analysis",
                phase="report",
                capability_tags=["report", "pptx", "csv"],
            ),
            handler=generate_report,
        ),
    ]
    registry.register(
        CalibrationPlugin(
            manifest=CalibrationPluginManifest(
                plugin_id="csv.file_analysis",
                display_name="CSV File Analysis",
                equipment_type="generic_semiconductor_tool",
                description="General CSV file analysis plugin for parsing, profiling, charting, diagnosis, and PPT report generation.",
                supported_models=["*"],
            ),
            tools=tools,
        )
    )


def _service(context: ToolContext) -> CSVDiagnosticService:
    return CSVDiagnosticService(generated_root=context.generated_root)


def _active_dataset(context: ToolContext):
    if context.active_dataset is None:
        raise ValueError("Current tool requires an active dataset.")
    if context.active_dataset.case_id != context.case_id:
        raise ValueError("Active dataset does not belong to the current case.")
    return context.active_dataset


def parse_dataset(context: ToolContext, arguments: dict[str, Any]) -> ToolResult:
    dataset = _active_dataset(context)
    service = _service(context)
    artifact = service.parse_dataset(case_id=context.case_id, dataset_id=dataset.id, path=dataset.path)
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
            for item in service.extract_metric_points(case_id=context.case_id, dataset_id=dataset.id, path=dataset.path)
        ]
        metric_point_count = context.metric_repository.replace_dataset_points(dataset.id, points)
    return ToolResult(
        summary=f"{artifact.summary} Stored {metric_point_count} metric point(s)."
        if context.metric_repository is not None
        else artifact.summary,
        data={
            "columns": artifact.data.get("columns", []),
            "row_count": artifact.data.get("row_count", 0),
            "preview": artifact.data.get("rows", [])[:5],
            "metric_point_count": metric_point_count,
        },
        artifacts=[artifact],
        artifact_ids=[artifact.id],
        next_suggestions=["inspect_dataset", "profile_dataset"],
    )


def inspect_dataset(context: ToolContext, arguments: dict[str, Any]) -> ToolResult:
    dataset = _active_dataset(context)
    artifact = _service(context).inspect_dataset(case_id=context.case_id, dataset_id=dataset.id, path=dataset.path)
    return ToolResult(
        summary=artifact.summary,
        data={
            "columns": artifact.data.get("columns", []),
            "column_types": artifact.data.get("column_types", {}),
            "numeric_columns": artifact.data.get("numeric_columns", []),
            "row_count": artifact.data.get("row_count", 0),
            "preview": artifact.data.get("preview", []),
        },
        artifacts=[artifact],
        artifact_ids=[artifact.id],
        next_suggestions=["profile_dataset", "build_trend_chart"],
    )


def profile_dataset(context: ToolContext, arguments: dict[str, Any]) -> ToolResult:
    dataset = _active_dataset(context)
    artifact, evidence = _service(context).profile_dataset(case_id=context.case_id, dataset_id=dataset.id, path=dataset.path)
    return ToolResult(
        summary=artifact.summary,
        data={
            "profile": artifact.data.get("profile", {}),
            "evidence": [{"id": item.id, "title": item.title, "summary": item.summary} for item in evidence],
        },
        artifacts=[artifact],
        evidence=evidence,
        artifact_ids=[artifact.id],
        evidence_ids=[item.id for item in evidence],
        next_suggestions=["build_trend_chart", "diagnose_performance"],
    )


def build_trend_chart(context: ToolContext, arguments: dict[str, Any]) -> ToolResult:
    dataset = _active_dataset(context)
    artifacts = _service(context).build_chart(case_id=context.case_id, dataset_id=dataset.id, path=dataset.path)
    chart_artifacts = [artifact for artifact in artifacts if artifact.kind == "chart"]
    image_charts = [artifact for artifact in chart_artifacts if artifact.data.get("render_type") == "image"]
    summary = f"Generated {len(image_charts)} Matplotlib chart file(s)." if image_charts else artifacts[0].summary
    return ToolResult(
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
        artifacts=artifacts,
        artifact_ids=[artifact.id for artifact in artifacts],
        next_suggestions=["diagnose_performance"],
    )


def diagnose_performance(context: ToolContext, arguments: dict[str, Any]) -> ToolResult:
    artifacts = context.repository.list_case_artifacts(context.case_id)
    profile = next((item for item in reversed(artifacts) if item.kind == "table" and "profile" in item.data), None)
    if profile is None:
        raise ValueError("profile_dataset must run before diagnose_performance")
    evidence = context.repository.list_case_evidence(context.case_id)
    artifact, conclusion = _service(context).diagnose(case_id=context.case_id, profile_artifact=profile, evidence=evidence)
    return ToolResult(
        summary=artifact.summary,
        data={
            "title": conclusion.title,
            "possible_causes": conclusion.possible_causes,
            "confidence": conclusion.confidence,
            "risk_level": conclusion.risk_level,
            "recommendations": conclusion.recommendations,
            "evidence_ids": conclusion.evidence_ids,
        },
        artifacts=[artifact],
        artifact_ids=[artifact.id],
        evidence_ids=conclusion.evidence_ids,
        next_suggestions=["generate_report"],
    )


def generate_report(context: ToolContext, arguments: dict[str, Any]) -> ToolResult:
    artifacts = context.repository.list_case_artifacts(context.case_id)
    evidence = context.repository.list_case_evidence(context.case_id)
    artifact = _service(context).generate_report(case_id=context.case_id, artifacts=artifacts, evidence=evidence)
    return ToolResult(
        summary=artifact.summary,
        data={
            "sections": [section.get("heading") for section in artifact.data.get("sections", [])],
            "format": artifact.data.get("format"),
            "mime_type": artifact.data.get("mime_type"),
            "chart_count": artifact.data.get("chart_count", 0),
            "template_engine": artifact.data.get("template_engine"),
            "filename": artifact.data.get("filename"),
        },
        artifacts=[artifact],
        artifact_ids=[artifact.id],
    )
