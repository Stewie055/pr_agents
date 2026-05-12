from __future__ import annotations

from typing import Any

from business.services.demo_csv_diagnostics import CSVDiagnosticService
from semidiag.infrastructure.metrics import MetricPoint
from semidiag.plugins import CalibrationPlugin, CalibrationPluginManifest
from semidiag.tools import ToolContext, ToolDefinition, ToolObservation, ToolRegistry, ToolResult

SYSTEM_DATASET_SCHEMA = {
    "type": "object",
    "properties": {"dataset_id": {"type": "string", "description": "System-selected active dataset id."}},
    "required": ["dataset_id"],
    "additionalProperties": False,
}


def register(registry):
    registry.register(
        CalibrationPlugin(
            manifest=CalibrationPluginManifest(
                plugin_id="demo.csv_diagnostics",
                display_name="Demo CSV Diagnostics",
                equipment_type="generic_semiconductor_tool",
                description="Non-confidential CSV diagnostic demo for parser, profiling, charting, diagnosis, and PPT report flow.",
                scenarios=[],
                log_kinds=[],
                supported_models=["*"],
                tool_names=[
                    "parse_dataset",
                    "inspect_dataset",
                    "profile_dataset",
                    "build_trend_chart",
                    "diagnose_performance",
                    "generate_report",
                ],
            ),
            build_tools=build_tools,
        )
    )


def build_tools(context: ToolContext | None) -> ToolRegistry:
    tools = ToolRegistry()
    tools.register(
        ToolDefinition(
            name="parse_dataset",
            description=(
                "Parse the current uploaded equipment performance CSV file and create a dataset artifact. "
                "Use this before profiling or diagnosis if the dataset has not been parsed."
            ),
            input_schema=SYSTEM_DATASET_SCHEMA,
            output_schema={"type": "object", "properties": {"artifact": {"type": "string", "const": "dataset"}}},
            origin="business:demo.csv_diagnostics",
            phase="parse",
            capability_tags=["csv", "dataset", "demo"],
            system_injected_args=["dataset_id"],
        ),
        parse_dataset,
    )
    tools.register(
        ToolDefinition(
            name="inspect_dataset",
            description=(
                "Inspect current dataset schema, column names, column types, row count, and a small preview. "
                "Use this when you need to understand fields or sample rows before analysis."
            ),
            input_schema=SYSTEM_DATASET_SCHEMA,
            output_schema={"type": "object", "properties": {"artifact": {"type": "string", "const": "table"}}},
            origin="business:demo.csv_diagnostics",
            phase="parse",
            capability_tags=["csv", "schema", "demo"],
            system_injected_args=["dataset_id"],
        ),
        inspect_dataset,
    )
    tools.register(
        ToolDefinition(
            name="profile_dataset",
            description=(
                "Profile numeric equipment metrics and collect evidence such as variance and outlier signals. "
                "Use this after parsing or inspecting the dataset."
            ),
            input_schema=SYSTEM_DATASET_SCHEMA,
            output_schema={"type": "object", "properties": {"artifact": {"type": "string", "const": "table"}}},
            origin="business:demo.csv_diagnostics",
            phase="analyze",
            capability_tags=["csv", "profile", "demo"],
            system_injected_args=["dataset_id"],
        ),
        profile_dataset,
    )
    tools.register(
        ToolDefinition(
            name="build_trend_chart",
            description="Generate Matplotlib PNG trend charts for current numeric equipment metrics when visual analysis is needed.",
            input_schema=SYSTEM_DATASET_SCHEMA,
            output_schema={"type": "object", "properties": {"artifact": {"type": "string", "const": "chart"}}},
            origin="business:demo.csv_diagnostics",
            phase="plot",
            capability_tags=["csv", "chart", "matplotlib", "demo"],
            system_injected_args=["dataset_id"],
        ),
        build_trend_chart,
    )
    tools.register(
        ToolDefinition(
            name="diagnose_performance",
            description=(
                "Generate a preliminary equipment performance diagnosis from existing profile artifacts and evidence. "
                "Use this after profile_dataset has produced metric evidence."
            ),
            input_schema={"type": "object", "properties": {}, "additionalProperties": False},
            output_schema={"type": "object", "properties": {"artifact": {"type": "string", "const": "diagnosis"}}},
            origin="business:demo.csv_diagnostics",
            phase="diagnose",
            capability_tags=["diagnosis", "demo"],
        ),
        diagnose_performance,
    )
    tools.register(
        ToolDefinition(
            name="generate_report",
            description="Generate an editable PPTX diagnostic report draft after analysis or diagnosis artifacts are available.",
            input_schema={"type": "object", "properties": {}, "additionalProperties": False},
            output_schema={"type": "object", "properties": {"artifact": {"type": "string", "const": "report"}}},
            origin="business:demo.csv_diagnostics",
            phase="report",
            capability_tags=["report", "pptx", "demo"],
        ),
        generate_report,
    )
    return tools


def _service(context: ToolContext) -> CSVDiagnosticService:
    return CSVDiagnosticService(generated_root=context.generated_root)


def _dataset(context: ToolContext, dataset_id: str):
    dataset = context.repository.get_dataset(dataset_id)
    if dataset is None or dataset.case_id != context.case_id:
        raise ValueError(f"Dataset not found for case: {dataset_id}")
    return dataset


def parse_dataset(context: ToolContext, arguments: dict[str, Any]) -> ToolResult:
    dataset = _dataset(context, arguments["dataset_id"])
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


def inspect_dataset(context: ToolContext, arguments: dict[str, Any]) -> ToolResult:
    dataset = _dataset(context, arguments["dataset_id"])
    artifact = _service(context).inspect_dataset(case_id=context.case_id, dataset_id=dataset.id, path=dataset.path)
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


def profile_dataset(context: ToolContext, arguments: dict[str, Any]) -> ToolResult:
    dataset = _dataset(context, arguments["dataset_id"])
    artifact, evidence = _service(context).profile_dataset(case_id=context.case_id, dataset_id=dataset.id, path=dataset.path)
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


def build_trend_chart(context: ToolContext, arguments: dict[str, Any]) -> ToolResult:
    dataset = _dataset(context, arguments["dataset_id"])
    artifacts = _service(context).build_chart(case_id=context.case_id, dataset_id=dataset.id, path=dataset.path)
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


def diagnose_performance(context: ToolContext, arguments: dict[str, Any]) -> ToolResult:
    artifacts = context.repository.list_case_artifacts(context.case_id)
    profile = next((item for item in reversed(artifacts) if item.kind == "table" and "profile" in item.data), None)
    if profile is None:
        raise ValueError("profile_dataset must run before diagnose_performance")
    evidence = context.repository.list_case_evidence(context.case_id)
    artifact, conclusion = _service(context).diagnose(case_id=context.case_id, profile_artifact=profile, evidence=evidence)
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


def generate_report(context: ToolContext, arguments: dict[str, Any]) -> ToolResult:
    artifacts = context.repository.list_case_artifacts(context.case_id)
    evidence = context.repository.list_case_evidence(context.case_id)
    artifact = _service(context).generate_report(case_id=context.case_id, artifacts=artifacts, evidence=evidence)
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
                "filename": artifact.data.get("filename"),
            },
            artifact_ids=[artifact.id],
        ),
    )
