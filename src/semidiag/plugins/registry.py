from __future__ import annotations

from semidiag.plugins.base import DiagnosticPlugin


class PluginRegistry:
    def __init__(self, plugins: list[DiagnosticPlugin] | None = None) -> None:
        self._plugins: dict[str, DiagnosticPlugin] = {}
        for plugin in plugins or []:
            self.register(plugin)

    def register(self, plugin: DiagnosticPlugin) -> None:
        self._plugins[plugin.equipment_type] = plugin

    def get(self, equipment_type: str) -> DiagnosticPlugin | None:
        return self._plugins.get(equipment_type)

    def require(self, equipment_type: str) -> DiagnosticPlugin:
        plugin = self.get(equipment_type)
        if plugin is None:
            available = ", ".join(sorted(self._plugins)) or "none"
            raise KeyError(f"No diagnostic plugin registered for equipment_type={equipment_type}. Available: {available}")
        return plugin

    def list_plugins(self) -> list[DiagnosticPlugin]:
        return list(self._plugins.values())
