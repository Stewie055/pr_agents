from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from semidiag.tools.registry import ToolContext, ToolDefinition, ToolResult


class ToolGuardrail(Protocol):
    def before_call(self, context: ToolContext, definition: ToolDefinition, arguments: dict) -> None: ...

    def after_call(self, context: ToolContext, definition: ToolDefinition, result: ToolResult) -> None: ...


class DefaultToolGuardrail:
    def before_call(self, context: ToolContext, definition: ToolDefinition, arguments: dict) -> None:
        active_dataset = getattr(context, "active_dataset", None)
        if active_dataset is not None and active_dataset.case_id != context.case_id:
            raise ValueError("Active dataset does not belong to the current case.")
        if "dataset_id" in arguments and "dataset_id" not in definition.system_injected_args:
            raise ValueError("dataset_id is a system-managed argument and must not be supplied by the model or user.")
        dataset_id = arguments.get("dataset_id")
        if dataset_id:
            dataset = context.repository.get_dataset(str(dataset_id))
            if dataset is None:
                raise ValueError("System-injected dataset_id does not exist.")
            if dataset.case_id != context.case_id:
                raise ValueError("System-injected dataset_id does not belong to the current case.")

    def after_call(self, context: ToolContext, definition: ToolDefinition, result: ToolResult) -> None:
        if not result.summary.strip():
            raise ValueError("ToolResult.summary must not be empty.")
        has_structured_output = any(
            [
                bool(result.data),
                bool(result.artifacts),
                bool(result.evidence),
                bool(result.artifact_ids),
                bool(result.evidence_ids),
                bool(result.task_ids),
            ]
        )
        if not has_structured_output:
            raise ValueError("ToolResult must include structured data, artifacts, evidence, or references.")
