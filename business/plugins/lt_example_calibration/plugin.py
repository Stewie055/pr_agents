from __future__ import annotations

from semidiag.domain import AnalysisArtifact
from semidiag.tools import ToolDefinition, ToolResult, ToolSpec

TOOLS = [
    ToolSpec(
        definition=ToolDefinition(
            name="lt_example_offline_prepare",
            description="Prepare non-confidential example LT offline calibration data.",
            input_schema={"type": "object", "properties": {}, "additionalProperties": False},
            output_schema={"type": "object", "properties": {"artifact": {"type": "string", "const": "table"}}},
            origin="business:lt.example.offline_check",
            phase="prepare",
            capability_tags=["LT", "offline_setup", "example"],
        ),
        handler=lambda context, arguments: prepare(context, arguments),
    ),
    ToolSpec(
        definition=ToolDefinition(
            name="lt_example_offline_analyze",
            description="Run non-confidential example LT offline calibration analysis.",
            input_schema={"type": "object", "properties": {}, "additionalProperties": False},
            output_schema={"type": "object", "properties": {"artifact": {"type": "string", "const": "diagnosis"}}},
            origin="business:lt.example.offline_check",
            phase="analyze",
            capability_tags=["LT", "offline_setup", "example"],
        ),
        handler=lambda context, arguments: analyze(context, arguments),
    ),
]


def prepare(context, arguments):
    artifact = AnalysisArtifact(
        case_id=context.case_id,
        kind="table",
        title="Example LT offline prepared data",
        summary="Prepared example LT offline calibration data.",
        data={"example": True},
    )
    return ToolResult(
        summary=artifact.summary,
        data={"prepared": True},
        artifacts=[artifact],
        artifact_ids=[artifact.id],
        next_suggestions=["lt_example_offline_analyze"],
    )


def analyze(context, arguments):
    artifact = AnalysisArtifact(
        case_id=context.case_id,
        kind="diagnosis",
        title="Example LT offline analysis",
        summary="Generated example LT offline calibration analysis.",
        data={"risk_level": "low", "confidence": 0.5, "example": True},
    )
    return ToolResult(
        summary=artifact.summary,
        data={"risk_level": "low", "confidence": 0.5},
        artifacts=[artifact],
        artifact_ids=[artifact.id],
    )
