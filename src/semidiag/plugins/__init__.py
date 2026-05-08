"""Diagnostic plugin package abstractions."""

from semidiag.plugins.base import DiagnosticPlugin
from semidiag.plugins.generic_equipment import GenericEquipmentPlugin

__all__ = ["DiagnosticPlugin", "GenericEquipmentPlugin"]
