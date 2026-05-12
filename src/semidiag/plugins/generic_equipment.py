from __future__ import annotations

from semidiag.plugins.base import DiagnosticPlugin


class GenericEquipmentPlugin(DiagnosticPlugin):
    def __init__(self) -> None:
        super().__init__(
            equipment_type="generic_semiconductor_tool",
            display_name="Generic semiconductor equipment",
        )


class LTEquipmentPlugin(DiagnosticPlugin):
    def __init__(self) -> None:
        super().__init__(equipment_type="LT", display_name="LT equipment")
