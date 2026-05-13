from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any

from pydantic import BaseModel, Field

from semidiag.domain import AnalysisArtifact, AuditEvent, DatasetRecord, DiagnosticCase, Evidence, ToolCallTrace
from semidiag.infrastructure.metrics import MetricRepository
from semidiag.infrastructure.repository import SQLiteRepository
from semidiag.tools.guardrails import DefaultToolGuardrail, ToolGuardrail


class ToolDefinition(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    required_permissions: list[str] = Field(default_factory=list)
    risk_level: str = "low"
    origin: str = "platform"
    phase: str = "general"
    capability_tags: list[str] = Field(default_factory=list)
    system_injected_args: list[str] = Field(default_factory=list)
    recovery_suggestions: list[str] = Field(default_factory=list)

    def llm_input_schema(self) -> dict[str, Any]:
        schema = dict(self.input_schema or {"type": "object", "properties": {}})
        injected = set(self.system_injected_args)
        if not injected:
            return schema
        properties = dict(schema.get("properties") or {})
        for name in injected:
            properties.pop(name, None)
        schema["properties"] = properties
        required = [name for name in schema.get("required", []) if name not in injected]
        if required:
            schema["required"] = required
        else:
            schema.pop("required", None)
        return schema

    def as_openai_tool(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.llm_input_schema(),
            },
        }


@dataclass
class ToolContext:
    case_id: str
    actor: str
    repository: SQLiteRepository
    case: DiagnosticCase | None = None
    datasets: list[DatasetRecord] = field(default_factory=list)
    active_dataset: DatasetRecord | None = None
    metric_repository: MetricRepository | None = None
    generated_root: str = "var/generated"


@dataclass
class ToolResult:
    summary: str
    data: dict[str, Any] = field(default_factory=dict)
    artifacts: list[AnalysisArtifact] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    artifact_ids: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    next_suggestions: list[str] = field(default_factory=list)


ToolHandler = Callable[[ToolContext, dict[str, Any]], ToolResult]


@dataclass
class ToolSpec:
    definition: ToolDefinition
    handler: ToolHandler


class ToolRegistry:
    def __init__(self, *, guardrails: list[ToolGuardrail] | None = None) -> None:
        self._definitions: dict[str, ToolDefinition] = {}
        self._handlers: dict[str, ToolHandler] = {}
        self._guardrails = guardrails if guardrails is not None else [DefaultToolGuardrail()]

    def register(self, definition: ToolDefinition, handler: ToolHandler) -> None:
        if definition.name in self._definitions:
            raise ValueError(f"Tool already registered: {definition.name}")
        self._definitions[definition.name] = definition
        self._handlers[definition.name] = handler

    def list_tools(self) -> list[ToolDefinition]:
        return list(self._definitions.values())

    def get_tool(self, name: str) -> ToolDefinition | None:
        return self._definitions.get(name)

    def get_handler(self, name: str) -> ToolHandler | None:
        return self._handlers.get(name)

    def extend(self, other: ToolRegistry) -> None:
        for definition in other.list_tools():
            handler = other.get_handler(definition.name)
            if handler is not None:
                self.register(definition, handler)

    def scoped(self, names: set[str]) -> ToolRegistry:
        registry = ToolRegistry()
        for definition in self.list_tools():
            if definition.name not in names:
                continue
            handler = self.get_handler(definition.name)
            if handler is not None:
                registry.register(definition, handler)
        return registry

    def openai_tools(self) -> list[dict[str, Any]]:
        return [definition.as_openai_tool() for definition in self.list_tools()]

    def prompt_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": definition.name,
                "description": definition.description,
                "input_schema": definition.llm_input_schema(),
                "output_schema": definition.output_schema or {"type": "object", "properties": {}},
                "risk_level": definition.risk_level,
                "origin": definition.origin,
                "phase": definition.phase,
                "capability_tags": definition.capability_tags,
                "recovery_suggestions": definition.recovery_suggestions,
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
            for guardrail in self._guardrails:
                guardrail.before_call(context, definition, arguments)
            result = self._handlers[name](context, arguments)
            for guardrail in self._guardrails:
                guardrail.after_call(context, definition, result)
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
    return ToolRegistry()
