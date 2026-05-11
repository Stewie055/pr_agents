from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Callable

from pydantic import BaseModel, Field

from semidiag.domain import AnalysisArtifact, AuditEvent, Evidence, ToolCallTrace
from semidiag.infrastructure.repository import SQLiteRepository
from semidiag.plugins import DiagnosticPlugin, GenericEquipmentPlugin


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


@dataclass
class ToolResult:
    summary: str
    artifacts: list[AnalysisArtifact] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)


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
            description="Parse an uploaded equipment performance CSV file.",
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
            name="profile_dataset",
            description="Profile numeric equipment metrics and collect evidence.",
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
            description="Build chart-ready trend data for numeric equipment metrics.",
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
            description="Generate preliminary diagnosis from artifacts and evidence.",
            input_schema={"type": "object", "properties": {}, "additionalProperties": False},
            output_schema={"type": "object", "properties": {"artifact": {"type": "string", "const": "diagnosis"}}},
        ),
        _diagnose_performance,
    )
    registry.register(
        ToolDefinition(
            name="generate_report",
            description="Generate an editable diagnostic report draft.",
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
    return ToolResult(summary=artifact.summary, artifacts=[artifact], payload={"artifact_id": artifact.id})


def _profile_dataset(context: ToolContext, arguments: dict[str, Any]) -> ToolResult:
    dataset = _dataset(context, arguments["dataset_id"])
    artifact, evidence = context.plugin.diagnostic_service().profile_dataset(
        case_id=context.case_id,
        dataset_id=dataset.id,
        path=dataset.path,
    )
    return ToolResult(summary=artifact.summary, artifacts=[artifact], evidence=evidence, payload={"artifact_id": artifact.id})


def _build_trend_chart(context: ToolContext, arguments: dict[str, Any]) -> ToolResult:
    dataset = _dataset(context, arguments["dataset_id"])
    artifact = context.plugin.diagnostic_service().build_chart(
        case_id=context.case_id,
        dataset_id=dataset.id,
        path=dataset.path,
    )
    return ToolResult(summary=artifact.summary, artifacts=[artifact], payload={"artifact_id": artifact.id})


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
    )


def _generate_report(context: ToolContext, arguments: dict[str, Any]) -> ToolResult:
    artifacts = context.repository.list_case_artifacts(context.case_id)
    evidence = context.repository.list_case_evidence(context.case_id)
    artifact = context.plugin.diagnostic_service().generate_report(
        case_id=context.case_id,
        artifacts=artifacts,
        evidence=evidence,
    )
    return ToolResult(summary=artifact.summary, artifacts=[artifact], payload={"artifact_id": artifact.id})
