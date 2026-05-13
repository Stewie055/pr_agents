from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

from semidiag.plugins.skills import SkillSpec
from semidiag.tools.registry import ToolContext, ToolRegistry, ToolSpec

LogKind = Literal["LT-D", "LT-C", "LT-R"]
LTScenario = Literal["offline_setup", "online_production"]
PluginStatus = Literal["ready", "degraded", "error"]


class CalibrationPluginManifest(BaseModel):
    plugin_id: str
    display_name: str
    equipment_type: str = "LT"
    description: str = ""
    scenarios: list[LTScenario] = Field(default_factory=list)
    log_kinds: list[LogKind] = Field(default_factory=list)
    supported_models: list[str] = Field(default_factory=lambda: ["*"])
    tool_names: list[str] = Field(default_factory=list)
    skill_names: list[str] = Field(default_factory=list)
    capability_tags: list[str] = Field(default_factory=list)
    requires_config: list[str] = Field(default_factory=list)
    max_tools: int = 6


@dataclass
class CalibrationPlugin:
    manifest: CalibrationPluginManifest
    tools: list[ToolSpec] = field(default_factory=list)
    skills: list[SkillSpec] = field(default_factory=list)
    status: PluginStatus = "ready"
    config_errors: list[str] = field(default_factory=list)
    implementation_path: str | None = None

    def __post_init__(self) -> None:
        if not self.manifest.tool_names:
            self.manifest.tool_names = [tool.definition.name for tool in self.tools]
        if not self.manifest.skill_names:
            self.manifest.skill_names = [skill.name for skill in self.skills]


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

    def attach_skill(self, skill: SkillSpec) -> None:
        plugin = self._plugins.get(skill.plugin_id)
        if plugin is None:
            raise KeyError(f"No calibration plugin registered for skill plugin_id={skill.plugin_id}")
        if any(existing.name == skill.name for existing in plugin.skills):
            raise ValueError(f"Skill already registered for plugin {skill.plugin_id}: {skill.name}")
        plugin.skills.append(skill)
        if skill.name not in plugin.manifest.skill_names:
            plugin.manifest.skill_names.append(skill.name)

    def get(self, plugin_id: str) -> CalibrationPlugin | None:
        return self._plugins.get(plugin_id)

    def list_plugins(self) -> list[CalibrationPlugin]:
        return list(self._plugins.values())

    def list_ready_plugins(self) -> list[CalibrationPlugin]:
        return [plugin for plugin in self.list_plugins() if plugin.status == "ready"]

    def list_manifests(self) -> list[CalibrationPluginManifest]:
        return [plugin.manifest for plugin in self.list_plugins()]

    def list_ready_manifests(self) -> list[CalibrationPluginManifest]:
        return [plugin.manifest for plugin in self.list_ready_plugins()]

    def list_skills(self, plugin_ids: list[str] | None = None) -> list[SkillSpec]:
        allowed = set(plugin_ids) if plugin_ids is not None else None
        skills: list[SkillSpec] = []
        for plugin in self.list_plugins():
            if plugin.status != "ready":
                continue
            if allowed is not None and plugin.manifest.plugin_id not in allowed:
                continue
            skills.extend(plugin.skills)
        return skills


class ToolScopeBuilder:
    def __init__(self, *, common_registry: ToolRegistry, calibration_registry: CalibrationPluginRegistry, max_tools: int = 12) -> None:
        self.common_registry = common_registry
        self.calibration_registry = calibration_registry
        self.max_tools = max_tools

    def build(self, *, selected_plugin_ids: list[str], context: ToolContext | None = None) -> ToolRegistry:
        active = ToolRegistry()
        for plugin_id in selected_plugin_ids:
            plugin = self.calibration_registry.get(plugin_id)
            if plugin is None or plugin.status != "ready":
                continue
            plugin_tools = self._plugin_tools(plugin)
            manifest_names = set(plugin.manifest.tool_names)
            actual_names = {definition.name for definition in plugin_tools.list_tools()}
            missing = manifest_names - actual_names
            if missing:
                raise ValueError(f"Plugin {plugin_id} manifest declares missing tool(s): {', '.join(sorted(missing))}")
            active.extend(plugin_tools)
            if len(active.list_tools()) >= self.max_tools:
                break
        for definition in self.common_registry.list_tools():
            if len(active.list_tools()) >= self.max_tools:
                break
            handler = self.common_registry.get_handler(definition.name)
            if handler is not None and active.get_tool(definition.name) is None:
                active.register(definition, handler)
        if len(active.list_tools()) <= self.max_tools:
            return active
        allowed = {definition.name for definition in active.list_tools()[: self.max_tools]}
        return active.scoped(allowed)

    def _plugin_tools(self, plugin: CalibrationPlugin) -> ToolRegistry:
        registry = ToolRegistry()
        for spec in plugin.tools:
            registry.register(spec.definition, spec.handler)
        return registry
