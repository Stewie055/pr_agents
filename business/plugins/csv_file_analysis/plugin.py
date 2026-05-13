from __future__ import annotations

from typing import Any

from business.services.csv_file_analysis import CSVDiagnosticService
from semidiag.infrastructure.metrics import MetricPoint
from semidiag.tools import ToolContext, ToolDefinition, ToolResult, ToolSpec

TOOLS = [
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
                system_injected_args=["dataset_id"],
                recovery_suggestions=["inspect_dataset"],
            ),
            handler=lambda context, arguments: parse_dataset(context, arguments),
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
                system_injected_args=["dataset_id"],
                recovery_suggestions=["parse_dataset"],
            ),
            handler=lambda context, arguments: inspect_dataset(context, arguments),
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
                system_injected_args=["dataset_id"],
                recovery_suggestions=["inspect_dataset", "parse_dataset"],
            ),
            handler=lambda context, arguments: profile_dataset(context, arguments),
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
                system_injected_args=["dataset_id"],
                recovery_suggestions=["inspect_dataset", "profile_dataset"],
            ),
            handler=lambda context, arguments: build_trend_chart(context, arguments),
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
                system_injected_args=["dataset_id"],
                recovery_suggestions=["profile_dataset", "build_trend_chart"],
            ),
            handler=lambda context, arguments: diagnose_performance(context, arguments),
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
                system_injected_args=["dataset_id"],
            ),
            handler=lambda context, arguments: generate_report(context, arguments),
        ),
]


def _service(context: ToolContext) -> CSVDiagnosticService:
    return CSVDiagnosticService(generated_root=context.generated_root)


def _active_dataset(context: ToolContext):
    if context.active_dataset is None:
        raise ValueError("Current tool requires an active dataset.")
    if context.active_dataset.case_id != context.case_id:
        raise ValueError("Active dataset does not belong to the current case.")
    return context.active_dataset


def _submit_task(context: ToolContext, *, name: str, payload: dict[str, Any], handler):
    if context.task_queue is None:
        raise ValueError("Task queue is not available for asynchronous tool execution.")
    return context.task_queue.submit(name=name, payload=payload, handler=handler)


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
    repository = context.repository
    generated_root = context.generated_root

    def run_chart_task(payload: dict[str, Any]) -> dict[str, Any]:
        service = CSVDiagnosticService(generated_root=generated_root)
        artifacts = service.build_chart(
            case_id=str(payload["case_id"]),
            dataset_id=str(payload["dataset_id"]),
            path=str(payload["path"]),
        )
        for artifact in artifacts:
            repository.add_artifact(artifact)
        chart_artifacts = [artifact for artifact in artifacts if artifact.kind == "chart"]
        image_charts = [artifact for artifact in chart_artifacts if artifact.data.get("render_type") == "image"]
        return {
            "artifact_ids": [artifact.id for artifact in artifacts],
            "chart_count": len(image_charts),
            "render_type": "image" if image_charts else "none",
        }

    task = _submit_task(
        context,
        name="csv.build_trend_chart",
        payload={"case_id": context.case_id, "dataset_id": dataset.id, "path": dataset.path},
        handler=run_chart_task,
    )
    return ToolResult(
        summary="Submitted Matplotlib trend chart generation task.",
        data={
            "task_id": task.id,
            "task_name": task.name,
            "task_status": task.status,
            "expected_artifact_kind": "chart",
        },
        task_ids=[task.id],
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
    repository = context.repository
    generated_root = context.generated_root

    def run_report_task(payload: dict[str, Any]) -> dict[str, Any]:
        service = CSVDiagnosticService(generated_root=generated_root)
        artifacts = repository.list_case_artifacts(str(payload["case_id"]))
        evidence = repository.list_case_evidence(str(payload["case_id"]))
        artifact = service.generate_report(case_id=str(payload["case_id"]), artifacts=artifacts, evidence=evidence)
        repository.add_artifact(artifact)
        return {
            "artifact_ids": [artifact.id],
            "format": artifact.data.get("format"),
            "mime_type": artifact.data.get("mime_type"),
            "filename": artifact.data.get("filename"),
        }

    task = _submit_task(
        context,
        name="csv.generate_report",
        payload={"case_id": context.case_id},
        handler=run_report_task,
    )
    return ToolResult(
        summary="Submitted PPTX diagnostic report generation task.",
        data={
            "task_id": task.id,
            "task_name": task.name,
            "task_status": task.status,
            "expected_artifact_kind": "report",
        },
        task_ids=[task.id],
    )
