from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DiagnosticPlugin:
    equipment_type: str
    display_name: str
