from __future__ import annotations

from fastapi.testclient import TestClient

from semidiag.agent import AgentRuntime
from semidiag.agent.llm import LLMResult, LLMToolCall
from semidiag.api.main import AppState, create_app
from semidiag.extensions import ExtensionLoader
from semidiag.plugins import CalibrationPluginRegistry, ToolScopeBuilder
from semidiag.tools import ToolRegistry, build_default_registry


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


def test_calibration_plugin_registry_lists_manifests_without_building_tools(tmp_path):
    plugins_dir = tmp_path / "business" / "plugins"
    plugins_dir.mkdir(parents=True)
    (plugins_dir / "calibration.py").write_text(
        """
from semidiag.plugins import CalibrationPlugin, CalibrationPluginManifest

called = False

def build_tools(context):
    global called
    called = True
    raise RuntimeError("tools should be lazy")

def register(registry):
    registry.register(
        CalibrationPlugin(
            manifest=CalibrationPluginManifest(plugin_id="lt.lazy", display_name="Lazy", log_kinds=["LT-D"]),
            build_tools=build_tools,
        )
    )
""",
        encoding="utf-8",
    )
    registry = CalibrationPluginRegistry()

    ExtensionLoader(tmp_path / "business").load_plugins(registry)

    assert registry.list_manifests()[0].plugin_id == "lt.lazy"


def test_tool_scope_builder_exposes_only_common_and_selected_plugin_tools(tmp_path):
    state = AppState(tmp_path)
    scoped = ToolScopeBuilder(common_registry=build_default_registry(), calibration_registry=state.calibration_registry).build(
        selected_plugin_ids=[]
    )
    scoped_names = {tool.name for tool in scoped.list_tools()}

    assert "parse_dataset" in scoped_names
    assert "lt_example_offline_analyze" not in scoped_names

    selected = ToolScopeBuilder(common_registry=build_default_registry(), calibration_registry=state.calibration_registry).build(
        selected_plugin_ids=["lt.example.offline_check"]
    )
    selected_names = {tool.name for tool in selected.list_tools()}
    assert "parse_dataset" in selected_names
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
    assert extensions.status_code == 200
    assert any(item["status"] == "loaded" for item in extensions.json()["extensions"])
    assert tools.status_code == 200
    assert any(item["name"] == "lt_list_log_pool" for item in tools.json()["tools"])


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
