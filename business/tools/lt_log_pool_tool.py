from __future__ import annotations

from semidiag.tools import ToolDefinition, ToolResult


def register(registry):
    registry.register(
        ToolDefinition(
            name="lt_list_log_pool",
            description="List LT log files uploaded to the current case with detected log kind and scenario metadata.",
            input_schema={"type": "object", "properties": {}, "additionalProperties": False},
            output_schema={"type": "object", "properties": {"logs": {"type": "array"}}},
        ),
        list_log_pool,
    )


def list_log_pool(context, arguments):
    datasets = context.repository.list_case_datasets(context.case_id)
    logs = [
        {
            "filename": dataset.filename,
            "log_kind": dataset.log_kind,
            "scenario": dataset.scenario,
            "matched_rule": dataset.matched_rule,
        }
        for dataset in datasets
    ]
    return ToolResult(
        summary=f"Found {len(logs)} LT log file(s) in the current case.",
        data={"logs": logs},
        next_suggestions=["select_calibration_plugin"],
    )
