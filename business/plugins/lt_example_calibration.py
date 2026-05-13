from __future__ import annotations

from semidiag.domain import AnalysisArtifact
from semidiag.plugins import CalibrationPlugin, CalibrationPluginManifest
from semidiag.tools import ToolDefinition, ToolResult, ToolSpec


def register(registry):
    tools = [
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
            handler=prepare,
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
            handler=analyze,
        ),
    ]
    registry.register(
        CalibrationPlugin(
            manifest=CalibrationPluginManifest(
                plugin_id="lt.example.offline_check",
                display_name="LT Example Offline Check",
                description="Non-confidential example calibration plugin for LT-C and LT-R offline setup logs.",
                scenarios=["offline_setup"],
                log_kinds=["LT-C", "LT-R"],
                supported_models=["*"],
            ),
            tools=tools,
        )
    )


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
