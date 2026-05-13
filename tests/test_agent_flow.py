from __future__ import annotations

from pathlib import Path

from semidiag.agent import AgentRuntime
from semidiag.extensions import ExtensionLoader
from semidiag.infrastructure.file_store import LocalFileStore
from semidiag.infrastructure.repository import SQLiteRepository
from semidiag.plugins import CalibrationPluginRegistry, GenericEquipmentPlugin, PluginRegistry
from semidiag.tools import build_default_registry
from tests.fakes import DeterministicLLMProvider

CSV_CONTENT = b"""timestamp,chamber_temperature,pressure,throughput
1,70,10,100
2,71,11,101
3,95,18,70
4,72,10,99
5,73,11,98
"""


class CustomEquipmentPlugin(GenericEquipmentPlugin):
    def __init__(self) -> None:
        super().__init__()
        self.equipment_type = "custom_semiconductor_tool"
        self.display_name = "Custom semiconductor equipment"


def load_demo_calibrations() -> CalibrationPluginRegistry:
    registry = CalibrationPluginRegistry()
    ExtensionLoader("business").load_plugins(registry)
    return registry


def wait_for_tasks(runtime: AgentRuntime) -> None:
    for task in runtime.task_queue.list_tasks():
        runtime.task_queue.wait(task.id, timeout=30)


def test_agent_runs_diagnostic_tool_loop(tmp_path):
    repository = SQLiteRepository(tmp_path / "test.sqlite3")
    file_store = LocalFileStore(tmp_path / "files")
    case = repository.create_case("Chamber performance drift")
    dataset = file_store.save_bytes(
        case_id=case.id,
        filename="performance.csv",
        content=CSV_CONTENT,
        content_type="text/csv",
    )
    repository.add_dataset(dataset)

    runtime = AgentRuntime(
        repository,
        llm=DeterministicLLMProvider(),
        registry=build_default_registry(),
        generated_root=str(tmp_path / "generated"),
        plugin=GenericEquipmentPlugin(),
        calibration_registry=load_demo_calibrations(),
    )
    result = runtime.handle_user_message(
        case_id=case.id,
        content="请诊断这份设备性能数据并给出建议",
        dataset_id=dataset.id,
    )

    assert "辅助诊断" in result.message.content
    assert {trace.tool_name for trace in result.tool_traces} >= {
        "parse_dataset",
        "profile_dataset",
        "build_trend_chart",
        "diagnose_performance",
    }
    wait_for_tasks(runtime)
    artifacts = repository.list_case_artifacts(case.id)
    assert {artifact.kind for artifact in artifacts} >= {"dataset", "table", "chart", "diagnosis"}
    charts = [artifact for artifact in artifacts if artifact.kind == "chart" and artifact.data.get("render_type") == "image"]
    assert charts
    assert all((tmp_path / "generated") in Path(chart.data["file_path"]).parents for chart in charts)
    assert repository.list_case_evidence(case.id)


def test_agent_generates_report_when_requested(tmp_path):
    repository = SQLiteRepository(tmp_path / "test.sqlite3")
    file_store = LocalFileStore(tmp_path / "files")
    case = repository.create_case("Report case")
    dataset = file_store.save_bytes(
        case_id=case.id,
        filename="performance.csv",
        content=CSV_CONTENT,
        content_type="text/csv",
    )
    repository.add_dataset(dataset)

    runtime = AgentRuntime(
        repository,
        llm=DeterministicLLMProvider(),
        generated_root=str(tmp_path / "generated"),
        plugin=GenericEquipmentPlugin(),
        calibration_registry=load_demo_calibrations(),
    )
    runtime.handle_user_message(case_id=case.id, content="生成诊断报告", dataset_id=dataset.id)
    wait_for_tasks(runtime)

    reports = [artifact for artifact in repository.list_case_artifacts(case.id) if artifact.kind == "report"]
    assert reports
    assert reports[0].data["format"] == "pptx"
    assert reports[0].data["mime_type"] == "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    assert Path(reports[0].data["file_path"]).exists()
    assert reports[0].data["sections"][0]["heading"] == "Executive Summary"


def test_agent_selects_plugin_by_case_equipment_type(tmp_path):
    repository = SQLiteRepository(tmp_path / "test.sqlite3")
    file_store = LocalFileStore(tmp_path / "files")
    case = repository.create_case("Custom chamber drift", equipment_type="custom_semiconductor_tool")
    dataset = file_store.save_bytes(
        case_id=case.id,
        filename="performance.csv",
        content=CSV_CONTENT,
        content_type="text/csv",
    )
    repository.add_dataset(dataset)
    generated_root = tmp_path / "custom-generated"
    runtime = AgentRuntime(
        repository,
        llm=DeterministicLLMProvider(),
        registry=build_default_registry(),
        generated_root=str(generated_root),
        plugin_registry=PluginRegistry([CustomEquipmentPlugin()]),
        calibration_registry=load_demo_calibrations(),
    )

    runtime.handle_user_message(case_id=case.id, content="请分析趋势", dataset_id=dataset.id)
    wait_for_tasks(runtime)

    charts = [
        artifact
        for artifact in repository.list_case_artifacts(case.id)
        if artifact.kind == "chart" and artifact.data.get("render_type") == "image"
    ]
    assert charts
    assert all(generated_root in Path(chart.data["file_path"]).parents for chart in charts)


def test_sync_and_stream_react_paths_share_tool_behavior(tmp_path):
    sync_repository = SQLiteRepository(tmp_path / "sync.sqlite3")
    stream_repository = SQLiteRepository(tmp_path / "stream.sqlite3")
    sync_file_store = LocalFileStore(tmp_path / "sync-files")
    stream_file_store = LocalFileStore(tmp_path / "stream-files")

    sync_case = sync_repository.create_case("Sync diagnostic")
    stream_case = stream_repository.create_case("Stream diagnostic")
    sync_dataset = sync_file_store.save_bytes(
        case_id=sync_case.id,
        filename="performance.csv",
        content=CSV_CONTENT,
        content_type="text/csv",
    )
    stream_dataset = stream_file_store.save_bytes(
        case_id=stream_case.id,
        filename="performance.csv",
        content=CSV_CONTENT,
        content_type="text/csv",
    )
    sync_repository.add_dataset(sync_dataset)
    stream_repository.add_dataset(stream_dataset)

    sync_runtime = AgentRuntime(
        sync_repository,
        llm=DeterministicLLMProvider(),
        generated_root=str(tmp_path / "sync-generated"),
        plugin=GenericEquipmentPlugin(),
        calibration_registry=load_demo_calibrations(),
    )
    stream_runtime = AgentRuntime(
        stream_repository,
        llm=DeterministicLLMProvider(),
        generated_root=str(tmp_path / "stream-generated"),
        plugin=GenericEquipmentPlugin(),
        calibration_registry=load_demo_calibrations(),
    )

    sync_runtime.handle_user_message(
        case_id=sync_case.id,
        content="请诊断这份设备性能数据并给出建议",
        dataset_id=sync_dataset.id,
    )
    stream_events = list(
        stream_runtime.stream_user_message(
            case_id=stream_case.id,
            content="请诊断这份设备性能数据并给出建议",
            dataset_id=stream_dataset.id,
        )
    )
    wait_for_tasks(sync_runtime)
    wait_for_tasks(stream_runtime)

    sync_tool_names = [trace.tool_name for trace in sync_repository.list_case_tool_traces(sync_case.id)]
    stream_tool_names = [trace.tool_name for trace in stream_repository.list_case_tool_traces(stream_case.id)]
    assert stream_events[-1].event == "final"
    assert sync_tool_names == stream_tool_names
    assert [step.phase for step in sync_repository.list_case_agent_step_traces(sync_case.id)] == [
        step.phase for step in stream_repository.list_case_agent_step_traces(stream_case.id)
    ]
    assert {artifact.kind for artifact in sync_repository.list_case_artifacts(sync_case.id)} == {
        artifact.kind for artifact in stream_repository.list_case_artifacts(stream_case.id)
    }
