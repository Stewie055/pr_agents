from __future__ import annotations

from semidiag.domain import AnalysisArtifact
from semidiag.plugins import CalibrationPlugin, CalibrationPluginManifest
from semidiag.tools import ToolDefinition, ToolObservation, ToolRegistry, ToolResult


def register(registry):
    registry.register(
        CalibrationPlugin(
            manifest=CalibrationPluginManifest(
                plugin_id="lt.example.offline_check",
                display_name="LT Example Offline Check",
                description="Non-confidential example calibration plugin for LT-C and LT-R offline setup logs.",
                scenarios=["offline_setup"],
                log_kinds=["LT-C", "LT-R"],
                supported_models=["*"],
                tool_names=["lt_example_offline_prepare", "lt_example_offline_analyze"],
            ),
            build_tools=build_tools,
        )
    )


def build_tools(context):
    tools = ToolRegistry()
    tools.register(
        ToolDefinition(
            name="lt_example_offline_prepare",
            description="Prepare non-confidential example LT offline calibration data.",
            input_schema={"type": "object", "properties": {}, "additionalProperties": False},
            output_schema={"type": "object", "properties": {"artifact": {"type": "string", "const": "table"}}},
        ),
        prepare,
    )
    tools.register(
        ToolDefinition(
            name="lt_example_offline_analyze",
            description="Run non-confidential example LT offline calibration analysis.",
            input_schema={"type": "object", "properties": {}, "additionalProperties": False},
            output_schema={"type": "object", "properties": {"artifact": {"type": "string", "const": "diagnosis"}}},
        ),
        analyze,
    )
    return tools


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
        artifacts=[artifact],
        observation=ToolObservation(
            tool_name="lt_example_offline_prepare",
            summary=artifact.summary,
            data={"prepared": True},
            artifact_ids=[artifact.id],
            next_suggestions=["lt_example_offline_analyze"],
        ),
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
        artifacts=[artifact],
        observation=ToolObservation(
            tool_name="lt_example_offline_analyze",
            summary=artifact.summary,
            data={"risk_level": "low", "confidence": 0.5},
            artifact_ids=[artifact.id],
        ),
    )
