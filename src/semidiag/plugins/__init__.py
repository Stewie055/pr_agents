"""Diagnostic plugin package abstractions."""

from semidiag.plugins.base import DiagnosticPlugin
from semidiag.plugins.generic_equipment import GenericEquipmentPlugin
from semidiag.plugins.registry import PluginRegistry

__all__ = ["DiagnosticPlugin", "GenericEquipmentPlugin", "PluginRegistry"]
