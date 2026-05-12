from __future__ import annotations

import json
import re
from dataclasses import dataclass

from pydantic import ValidationError

from semidiag.agent.llm import LLMError, LLMProvider, StubLLMProvider
from semidiag.plugins.calibration import CalibrationPluginManifest, CalibrationPluginRegistry, CalibrationSelection


@dataclass
class PluginSelectionContext:
    user_content: str
    log_kinds: list[str]
    scenario: str | None
    model_variant: str | None


class PluginSelectorAgent:
    def __init__(self, llm: LLMProvider, registry: CalibrationPluginRegistry, *, max_plugins: int = 3) -> None:
        self.llm = llm
        self.registry = registry
        self.max_plugins = max_plugins

    def select(self, context: PluginSelectionContext) -> CalibrationSelection:
        manifests = self.registry.list_manifests()
        if not manifests:
            return CalibrationSelection(reason="No calibration plugins loaded.")
        if isinstance(self.llm, StubLLMProvider):
            return self._select_locally(context=context, manifests=manifests)

        messages = [
            {
                "role": "system",
                "content": (
                    "你是 LT 设备测校项插件选择器。只根据用户问题、日志元数据和插件 manifest 选择插件。"
                    "必须只输出 JSON，字段为 plugin_ids, reason, confidence。不要输出 Markdown。"
                    f"最多选择 {self.max_plugins} 个插件；不确定时返回空 plugin_ids 并说明需要澄清。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"User content: {context.user_content}\n"
                    f"Log kinds: {context.log_kinds}\n"
                    f"Scenario: {context.scenario}\n"
                    f"Model variant: {context.model_variant}\n"
                    f"Plugin manifests: {[manifest.model_dump(mode='json') for manifest in manifests]}"
                ),
            },
        ]
        result = self.llm.summarize_turn(messages=messages)
        match = re.search(r"\{.*\}", result.content, re.DOTALL)
        if not match:
            raise LLMError("Plugin selector did not return JSON", status_code=502)
        try:
            payload = json.loads(match.group(0))
            selection = CalibrationSelection(
                plugin_ids=[str(item) for item in payload.get("plugin_ids", [])][: self.max_plugins],
                reason=str(payload.get("reason", "")),
                confidence=float(payload.get("confidence", 0.0)),
            )
        except (TypeError, ValueError, json.JSONDecodeError, ValidationError) as exc:
            raise LLMError(f"Plugin selector returned invalid JSON: {exc}", status_code=502) from exc
        return self._filter_existing(selection)

    def _select_locally(
        self,
        *,
        context: PluginSelectionContext,
        manifests: list[CalibrationPluginManifest],
    ) -> CalibrationSelection:
        selected: list[str] = []
        normalized = context.user_content.lower()
        log_kinds = set(context.log_kinds)
        for manifest in manifests:
            if manifest.log_kinds and not log_kinds.intersection(manifest.log_kinds):
                continue
            if context.scenario and manifest.scenarios and context.scenario not in manifest.scenarios:
                continue
            haystack = f"{manifest.plugin_id} {manifest.display_name} {manifest.description}".lower()
            if any(token in haystack for token in normalized.split() if len(token) > 1) or not selected:
                selected.append(manifest.plugin_id)
            if len(selected) >= self.max_plugins:
                break
        if not selected:
            return CalibrationSelection(reason="No calibration plugin matched current logs and request.", confidence=0.0)
        return CalibrationSelection(plugin_ids=selected, reason="Matched calibration plugin manifest and log metadata.", confidence=0.7)

    def _filter_existing(self, selection: CalibrationSelection) -> CalibrationSelection:
        existing = {manifest.plugin_id for manifest in self.registry.list_manifests()}
        selection.plugin_ids = [plugin_id for plugin_id in selection.plugin_ids if plugin_id in existing][: self.max_plugins]
        return selection
