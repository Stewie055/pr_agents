"""Diagnostic plugin package abstractions."""

from semidiag.plugins.base import DiagnosticPlugin
from semidiag.plugins.calibration import (
    CalibrationPlugin,
    CalibrationPluginManifest,
    CalibrationPluginRegistry,
    CalibrationSelection,
    LogKind,
    LTScenario,
    ToolScopeBuilder,
)
from semidiag.plugins.generic_equipment import GenericEquipmentPlugin, LTEquipmentPlugin
from semidiag.plugins.registry import PluginRegistry
from semidiag.plugins.selector import PluginSelectionContext, PluginSelectorAgent
from semidiag.plugins.skills import SkillSpec, load_markdown_skill

__all__ = [
    "CalibrationPlugin",
    "CalibrationPluginManifest",
    "CalibrationPluginRegistry",
    "CalibrationSelection",
    "DiagnosticPlugin",
    "GenericEquipmentPlugin",
    "LogKind",
    "LTScenario",
    "LTEquipmentPlugin",
    "PluginRegistry",
    "PluginSelectionContext",
    "PluginSelectorAgent",
    "SkillSpec",
    "ToolScopeBuilder",
    "load_markdown_skill",
]
