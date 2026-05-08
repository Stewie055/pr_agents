from __future__ import annotations

from semidiag.agent import AgentRuntime
from semidiag.infrastructure.file_store import LocalFileStore
from semidiag.infrastructure.repository import SQLiteRepository
from semidiag.tools import build_default_registry


CSV_CONTENT = b"""timestamp,chamber_temperature,pressure,throughput
1,70,10,100
2,71,11,101
3,95,18,70
4,72,10,99
5,73,11,98
"""


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

    runtime = AgentRuntime(repository, registry=build_default_registry())
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
    assert {artifact.kind for artifact in result.artifacts} >= {"dataset", "table", "chart", "diagnosis"}
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

    runtime = AgentRuntime(repository)
    runtime.handle_user_message(case_id=case.id, content="生成诊断报告", dataset_id=dataset.id)

    reports = [artifact for artifact in repository.list_case_artifacts(case.id) if artifact.kind == "report"]
    assert reports
    assert reports[0].data["sections"][0]["heading"] == "Executive Summary"
