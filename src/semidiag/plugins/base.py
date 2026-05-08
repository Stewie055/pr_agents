from __future__ import annotations

from abc import ABC, abstractmethod

from semidiag.services.csv_diagnostics import CSVDiagnosticService


class DiagnosticPlugin(ABC):
    equipment_type: str
    display_name: str

    @abstractmethod
    def diagnostic_service(self) -> CSVDiagnosticService:
        raise NotImplementedError
