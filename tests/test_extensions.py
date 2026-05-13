from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

import semidiag.tools as tools_module
from business.file_classifiers.lt_log_metadata import detect_file_metadata
from semidiag.agent import AgentRuntime
from semidiag.agent.llm import LLMResult, LLMToolCall
from semidiag.api.main import AppState, create_app
from semidiag.extensions import ExtensionLoader
from semidiag.plugins import CalibrationPluginRegistry, ToolScopeBuilder
from semidiag.plugins.skills import load_markdown_skill
from semidiag.tools import ToolContext, ToolDefinition, ToolRegistry, ToolResult, ToolSpec, build_default_registry


def test_extension_loader_loads_business_tools(tmp_path):
    tools_dir = tmp_path / "business" / "tools"
    tools_dir.mkdir(parents=True)
    (tools_dir / "custom_tool.py").write_text(
        """
from semidiag.tools import ToolDefinition, ToolResult

def register(registry):
    registry.register(
        ToolDefinition(name="custom_tool", description="custom", input_schema={"type": "object"}),
        lambda context, arguments: ToolResult(summary="ok"),
    )
""",
        encoding="utf-8",
    )
    registry = ToolRegistry()

    report = ExtensionLoader(tmp_path / "business").load_tools(registry)

    assert registry.get_tool("custom_tool") is not None
    assert report.events[0].status == "loaded"


def test_extension_loader_records_bad_extension_without_failing_startup(tmp_path):
    tools_dir = tmp_path / "business" / "tools"
    tools_dir.mkdir(parents=True)
    (tools_dir / "bad_tool.py").write_text("BROKEN = True\n", encoding="utf-8")
    registry = ToolRegistry()

    report = ExtensionLoader(tmp_path / "business").load_tools(registry)

    assert report.events[0].status == "error"
    assert "register" in (report.events[0].error or "")


def test_calibration_plugin_registry_lists_manifests_without_running_tools(tmp_path):
    plugins_dir = tmp_path / "business" / "plugins"
    plugins_dir.mkdir(parents=True)
    (plugins_dir / "calibration.py").write_text(
        """
from semidiag.plugins import CalibrationPlugin, CalibrationPluginManifest
from semidiag.tools import ToolDefinition, ToolResult, ToolSpec

def lazy_tool(context, arguments):
    raise RuntimeError("tools should be lazy")

def register(registry):
    registry.register(
        CalibrationPlugin(
            manifest=CalibrationPluginManifest(plugin_id="lt.lazy", display_name="Lazy", log_kinds=["LT-D"]),
            tools=[ToolSpec(ToolDefinition(name="lt_lazy", description="lazy"), lazy_tool)],
        )
    )
""",
        encoding="utf-8",
    )
    registry = CalibrationPluginRegistry()

    ExtensionLoader(tmp_path / "business").load_plugins(registry)

    assert registry.list_manifests()[0].plugin_id == "lt.lazy"
    assert registry.list_manifests()[0].tool_names == ["lt_lazy"]


def test_extension_loader_loads_markdown_skills_for_plugins(tmp_path):
    plugins_dir = tmp_path / "business" / "plugins"
    skills_dir = plugins_dir / "calibration" / "skills"
    skills_dir.mkdir(parents=True)
    (plugins_dir / "calibration.py").write_text(
        """
from semidiag.plugins import CalibrationPlugin, CalibrationPluginManifest
from semidiag.tools import ToolDefinition, ToolResult, ToolSpec

def lazy_tool(context, arguments):
    return ToolResult(summary="ok", data={"ok": True})

def register(registry):
    registry.register(
        CalibrationPlugin(
            manifest=CalibrationPluginManifest(plugin_id="lt.lazy", display_name="Lazy"),
            tools=[ToolSpec(ToolDefinition(name="lt_lazy", description="lazy"), lazy_tool)],
        )
    )
""",
        encoding="utf-8",
    )
    (skills_dir / "lazy.md").write_text(
        """---
name: lt_lazy_skill
description: Lazy skill guidance.
plugin_id: lt.lazy
triggers: [lazy, test]
max_context_chars: 100
---

Use this lazy skill only for selected lazy plugin analysis.
""",
        encoding="utf-8",
    )
    registry = CalibrationPluginRegistry()
    loader = ExtensionLoader(tmp_path / "business")

    loader.load_plugins(registry)
    loader.load_plugin_skills(registry)

    plugin = registry.get("lt.lazy")
    assert plugin is not None
    assert plugin.manifest.skill_names == ["lt_lazy_skill"]
    assert plugin.skills[0].description == "Lazy skill guidance."
    assert any(event.extension_type == "skill" and event.status == "loaded" for event in loader.report.events)


def test_extension_loader_records_bad_markdown_skill(tmp_path):
    skills_dir = tmp_path / "business" / "plugins" / "missing" / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "bad.md").write_text("no frontmatter", encoding="utf-8")
    registry = CalibrationPluginRegistry()

    report = ExtensionLoader(tmp_path / "business").load_plugin_skills(registry)

    assert report.events[0].extension_type == "skill"
    assert report.events[0].status == "error"
    assert "frontmatter" in (report.events[0].error or "")


def test_markdown_skill_requires_known_plugin(tmp_path):
    skills_dir = tmp_path / "business" / "plugins" / "orphan" / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "orphan.md").write_text(
        """---
name: orphan
description: Orphan skill.
plugin_id: lt.unknown
---

No plugin owns this skill.
""",
        encoding="utf-8",
    )
    registry = CalibrationPluginRegistry()

    report = ExtensionLoader(tmp_path / "business").load_plugin_skills(registry)

    assert report.events[0].status == "error"
    assert "lt.unknown" in (report.events[0].error or "")


def test_tool_scope_builder_exposes_only_common_and_selected_plugin_tools(tmp_path):
    state = AppState(tmp_path)
    scoped = ToolScopeBuilder(common_registry=build_default_registry(), calibration_registry=state.calibration_registry).build(
        selected_plugin_ids=[]
    )
    scoped_names = {tool.name for tool in scoped.list_tools()}

    assert "parse_dataset" not in scoped_names
    assert "lt_example_offline_analyze" not in scoped_names

    selected = ToolScopeBuilder(common_registry=build_default_registry(), calibration_registry=state.calibration_registry).build(
        selected_plugin_ids=["lt.example.offline_check"]
    )
    selected_names = {tool.name for tool in selected.list_tools()}
    assert "lt_example_offline_analyze" in selected_names


def test_api_lists_calibrations_and_extension_errors(tmp_path):
    state = AppState(tmp_path)
    app = create_app(state)
    client = TestClient(app)

    calibrations = client.get("/api/calibrations")
    extensions = client.get("/api/extensions")
    tools = client.get("/api/tools")

    assert calibrations.status_code == 200
    assert any(item["plugin_id"] == "lt.example.offline_check" for item in calibrations.json()["calibrations"])
    assert any(item["skills"] for item in calibrations.json()["calibrations"] if item["plugin_id"] == "lt.example.offline_check")
    assert extensions.status_code == 200
    assert any(item["status"] == "loaded" for item in extensions.json()["extensions"])
    assert tools.status_code == 200
    assert any(item["name"] == "lt_list_log_pool" for item in tools.json()["tools"])


def test_tool_registry_rejects_duplicate_names():
    registry = ToolRegistry()
    definition = ToolDefinition(name="duplicate", description="first")
    registry.register(definition, lambda context, arguments: ToolResult(summary="ok"))

    try:
        registry.register(definition, lambda context, arguments: ToolResult(summary="bad"))
    except ValueError as exc:
        assert "duplicate" in str(exc)
    else:
        raise AssertionError("duplicate tool registration should fail")


def test_tool_guardrail_rejects_user_supplied_dataset_id(tmp_path):
    state = AppState(tmp_path)
    case = state.repository.create_case("Guardrail")
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(name="guarded", description="guarded"),
        lambda context, arguments: ToolResult(summary="ok", data={"ok": True}),
    )
    context = ToolContext(case_id=case.id, actor="engineer", repository=state.repository)

    try:
        registry.run("guarded", context, {"dataset_id": "user_supplied"})
    except ValueError as exc:
        assert "dataset_id" in str(exc)
    else:
        raise AssertionError("user supplied dataset_id should fail guardrail")

    assert state.repository.list_case_tool_traces(case.id)[0].status == "error"


def test_tool_guardrail_rejects_empty_structured_result(tmp_path):
    state = AppState(tmp_path)
    case = state.repository.create_case("Guardrail")
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(name="empty_result", description="empty"),
        lambda context, arguments: ToolResult(summary="ok"),
    )
    context = ToolContext(case_id=case.id, actor="engineer", repository=state.repository)

    try:
        registry.run("empty_result", context, {})
    except ValueError as exc:
        assert "structured" in str(exc)
    else:
        raise AssertionError("empty ToolResult should fail guardrail")


def test_system_injected_arguments_are_hidden_from_llm_schema():
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="hidden_dataset",
            description="hidden",
            input_schema={
                "type": "object",
                "properties": {
                    "dataset_id": {"type": "string"},
                    "visible": {"type": "string"},
                },
                "required": ["dataset_id", "visible"],
            },
            system_injected_args=["dataset_id"],
        ),
        lambda context, arguments: ToolResult(summary="ok"),
    )

    schema = registry.openai_tools()[0]["function"]["parameters"]

    assert "dataset_id" not in schema["properties"]
    assert schema["required"] == ["visible"]


def test_tool_scope_builder_validates_manifest_tool_names():
    registry = CalibrationPluginRegistry()

    from semidiag.plugins import CalibrationPlugin, CalibrationPluginManifest

    registry.register(
        CalibrationPlugin(
            manifest=CalibrationPluginManifest(
                plugin_id="bad.manifest",
                display_name="Bad",
                tool_names=["missing_tool"],
            ),
            tools=[
                ToolSpec(
                    ToolDefinition(name="actual_tool", description="actual"),
                    lambda tool_context, arguments: ToolResult(summary="ok"),
                )
            ],
        )
    )

    try:
        ToolScopeBuilder(common_registry=ToolRegistry(), calibration_registry=registry).build(
            selected_plugin_ids=["bad.manifest"]
        )
    except ValueError as exc:
        assert "missing_tool" in str(exc)
    else:
        raise AssertionError("manifest/tool mismatch should fail")


def test_tool_result_is_the_single_observation_payload():
    result = ToolResult(summary="ok", data={"value": 1}, artifact_ids=["art_1"], next_suggestions=["next_tool"])

    assert result.summary == "ok"
    assert result.data == {"value": 1}
    assert result.artifact_ids == ["art_1"]
    assert result.next_suggestions == ["next_tool"]
    assert not hasattr(tools_module, "ToolObservation")


def test_markdown_skill_parser_extracts_frontmatter(tmp_path):
    path = tmp_path / "skill.md"
    path.write_text(
        """---
name: parser_skill
description: Parser skill.
plugin_id: lt.parser
triggers: [a, b]
max_context_chars: 8
---

1234567890
""",
        encoding="utf-8",
    )

    skill = load_markdown_skill(path)

    assert skill.name == "parser_skill"
    assert skill.triggers == ["a", "b"]
    assert skill.context_excerpt() == "12345678"


def test_framework_source_does_not_embed_csv_analysis_tools():
    forbidden = {
        "parse_dataset",
        "inspect_dataset",
        "profile_dataset",
        "build_trend_chart",
        "diagnose_performance",
        "generate_report",
    }
    for path in Path("src/semidiag").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        matches = {name for name in forbidden if re.search(rf"\b{re.escape(name)}\b", text)}
        assert not matches, f"{path} contains framework-level CSV tool fallback(s): {sorted(matches)}"


def test_lt_file_metadata_detector_is_business_owned():
    metadata = detect_file_metadata(
        filename="tool_LT-D_20260513.log",
        content_type="text/plain",
        content_preview=b"sample",
    )

    assert metadata.log_kind == "LT-D"
    assert metadata.scenario == "online_production"
    assert metadata.matched_rule == "filename:LT-D"


class ScopedToolProvider:
    provider_name = "test"
    model = "scoped"
    tool_mode = "native"

    def __init__(self) -> None:
        self.plan_round = 0

    def tool_specs(self, registry):
        return registry.openai_tools()

    def summarize_turn(self, *, messages):
        if "插件选择器" in messages[0]["content"]:
            return LLMResult(content='{"plugin_ids":["lt.example.offline_check"],"reason":"test","confidence":0.9}')
        return LLMResult(
            content=(
                '{"intent":"diagnosis","requires_dataset":true,"requires_knowledge":false,'
                '"target_workflow":null,"user_goal":"offline check","response_style":"normal","reason":"test"}'
            )
        )

    def summarize_turn_stream(self, *, messages):
        yield from ()

    def plan_tool_calls(self, *, messages, tools):
        self.plan_round += 1
        if not any(item.get("role") == "tool" for item in messages):
            assert "Selected skill guidance" in messages[-1]["content"]
            assert "lt_example_offline_check" in messages[-1]["content"]
        tool_names = {tool["function"]["name"] for tool in tools}
        assert "lt_example_offline_analyze" in tool_names
        assert "lt_example_offline_prepare" in tool_names
        if self.plan_round == 1:
            return LLMResult(tool_calls=[LLMToolCall(id="call_1", name="lt_example_offline_analyze", arguments={})])
        return LLMResult(content="完成 scoped plugin tool 分析。")

    def plan_tool_calls_stream(self, *, messages, tools):
        yield from ()

    def assistant_plan_message(self, result):
        return {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {"name": call.name, "arguments": "{}"},
                }
                for call in result.tool_calls
            ],
        }

    def tool_observation_messages(self, observations):
        return [
            {
                "role": "tool",
                "tool_call_id": item["tool_call_id"],
                "name": item["tool_name"],
                "content": str(item["observation"]),
            }
            for item in observations
        ]


def test_react_loop_receives_scoped_tools_only(tmp_path):
    state = AppState(tmp_path)
    provider = ScopedToolProvider()
    state.agent = AgentRuntime(
        state.repository,
        registry=state.tool_registry,
        llm=provider,
        plugin_registry=state.plugin_registry,
        calibration_registry=state.calibration_registry,
        metric_repository=state.metric_repository,
    )
    case = state.repository.create_case("LT scoped", equipment_type="LT")
    dataset = state.file_store.save_bytes(
        case_id=case.id,
        filename="sample_LT-C.log",
        content=b"example",
        content_type="text/plain",
    )
    dataset.log_kind = "LT-C"
    dataset.scenario = "offline_setup"
    state.repository.add_dataset(dataset)

    result = state.agent.handle_user_message(case_id=case.id, content="offline check", dataset_id=dataset.id)

    assert result.message.content == "完成 scoped plugin tool 分析。"
    assert any(artifact.title == "Example LT offline analysis" for artifact in result.artifacts)
