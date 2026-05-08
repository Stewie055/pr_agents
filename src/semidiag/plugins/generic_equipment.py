from __future__ import annotations

from semidiag.plugins.base import DiagnosticPlugin
from semidiag.services.csv_diagnostics import CSVDiagnosticService


class GenericEquipmentPlugin(DiagnosticPlugin):
    equipment_type = "generic_semiconductor_tool"
    display_name = "Generic semiconductor equipment"

    def __init__(self) -> None:
        self._service = CSVDiagnosticService()

    def diagnostic_service(self) -> CSVDiagnosticService:
        return self._service
