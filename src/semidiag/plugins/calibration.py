from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

from semidiag.tools.registry import ToolContext, ToolRegistry

LogKind = Literal["LT-D", "LT-C", "LT-R"]
LTScenario = Literal["offline_setup", "online_production"]


class CalibrationPluginManifest(BaseModel):
    plugin_id: str
    display_name: str
    equipment_type: str = "LT"
    description: str = ""
    scenarios: list[LTScenario] = Field(default_factory=list)
    log_kinds: list[LogKind] = Field(default_factory=list)
    supported_models: list[str] = Field(default_factory=lambda: ["*"])
    tool_names: list[str] = Field(default_factory=list)
    max_tools: int = 6


ToolProvider = Callable[[ToolContext | None], ToolRegistry]


@dataclass
class CalibrationPlugin:
    manifest: CalibrationPluginManifest
    build_tools: ToolProvider


@dataclass
class CalibrationSelection:
    plugin_ids: list[str] = field(default_factory=list)
    reason: str = ""
    confidence: float = 0.0


class CalibrationPluginRegistry:
    def __init__(self) -> None:
        self._plugins: dict[str, CalibrationPlugin] = {}

    def register(self, plugin: CalibrationPlugin) -> None:
        self._plugins[plugin.manifest.plugin_id] = plugin

    def get(self, plugin_id: str) -> CalibrationPlugin | None:
        return self._plugins.get(plugin_id)

    def list_plugins(self) -> list[CalibrationPlugin]:
        return list(self._plugins.values())

    def list_manifests(self) -> list[CalibrationPluginManifest]:
        return [plugin.manifest for plugin in self.list_plugins()]


class ToolScopeBuilder:
    def __init__(self, *, common_registry: ToolRegistry, calibration_registry: CalibrationPluginRegistry, max_tools: int = 12) -> None:
        self.common_registry = common_registry
        self.calibration_registry = calibration_registry
        self.max_tools = max_tools

    def build(self, *, selected_plugin_ids: list[str], context: ToolContext | None = None) -> ToolRegistry:
        active = ToolRegistry()
        active.extend(self.common_registry)
        for plugin_id in selected_plugin_ids:
            plugin = self.calibration_registry.get(plugin_id)
            if plugin is None:
                continue
            active.extend(plugin.build_tools(context))
            if len(active.list_tools()) >= self.max_tools:
                break
        if len(active.list_tools()) <= self.max_tools:
            return active
        allowed = {definition.name for definition in active.list_tools()[: self.max_tools]}
        return active.scoped(allowed)
