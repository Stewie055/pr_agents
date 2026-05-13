from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LTLogMetadata:
    log_kind: str | None
    scenario: str | None
    matched_rule: str | None


def detect_file_metadata(
    *,
    filename: str,
    content_type: str | None = None,
    content_preview: bytes = b"",
) -> LTLogMetadata:
    normalized = filename.upper()
    if "LT-D" in normalized:
        return LTLogMetadata(log_kind="LT-D", scenario="online_production", matched_rule="filename:LT-D")
    if "LT-C" in normalized:
        return LTLogMetadata(log_kind="LT-C", scenario="offline_setup", matched_rule="filename:LT-C")
    if "LT-R" in normalized:
        return LTLogMetadata(log_kind="LT-R", scenario="offline_setup", matched_rule="filename:LT-R")
    return LTLogMetadata(log_kind=None, scenario=None, matched_rule=None)


def detect_lt_log_metadata(filename: str) -> LTLogMetadata:
    return detect_file_metadata(filename=filename)
