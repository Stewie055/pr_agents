from __future__ import annotations

import json

from fastapi.testclient import TestClient

from semidiag.agent import AgentRuntime
from semidiag.api.main import AppState, create_app
from semidiag.domain import AgentStepTrace, LLMAuditEvent
from tests.fakes import DeterministicLLMProvider

CSV_CONTENT = """timestamp,chamber_temperature,pressure,throughput
1,70,10,100
2,71,11,101
3,95,18,70
4,72,10,99
5,73,11,98
"""


def parse_sse_events(payload: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    for block in payload.strip().split("\n\n"):
        event = ""
        data = ""
        for line in block.splitlines():
            if line.startswith("event:"):
                event = line.removeprefix("event:").strip()
            if line.startswith("data:"):
                data = line.removeprefix("data:").strip()
        if event and data:
            events.append((event, json.loads(data)))
    return events


def wait_for_tasks(state: AppState) -> None:
    for task in state.task_queue.list_tasks():
        state.task_queue.wait(task.id, timeout=30)


def test_api_case_upload_and_agent_message(tmp_path):
    state = AppState(tmp_path)
    state.agent = AgentRuntime(
        state.repository,
        registry=state.tool_registry,
        llm=DeterministicLLMProvider(),
        generated_root=str(state.generated_root),
        plugin_registry=state.plugin_registry,
        calibration_registry=state.calibration_registry,
        metric_repository=state.metric_repository,
        task_queue=state.task_queue,
    )
    app = create_app(state)
    client = TestClient(app)

    created = client.post("/api/cases", json={"title": "Chamber drift"}).json()
    case_id = created["id"]

    upload = client.post(
        f"/api/cases/{case_id}/files",
        files={"file": ("performance.csv", CSV_CONTENT, "text/csv")},
    )
    assert upload.status_code == 200
    dataset_id = upload.json()["id"]

    response = client.post(
        f"/api/cases/{case_id}/messages",
        json={"content": "请分析并诊断", "dataset_id": dataset_id},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["message"]["role"] == "assistant"
    assert any(item["kind"] == "diagnosis" for item in body["artifacts"])
    wait_for_tasks(state)
    snapshot = client.get(f"/api/cases/{case_id}").json()
    assert any(item["kind"] == "chart" and item["data"]["render_type"] == "image" for item in snapshot["artifacts"])
    assert any(trace["tool_name"] == "diagnose_performance" for trace in body["tool_traces"])
    assert len(state.metric_repository.list_dataset_points(dataset_id)) == 20

    chart = next(item for item in snapshot["artifacts"] if item["kind"] == "chart" and item["data"]["render_type"] == "image")
    chart_file = client.get(f"/api/artifacts/{chart['id']}/file")
    assert chart_file.status_code == 200
    assert chart_file.headers["content-type"].startswith("image/png")
    assert chart_file.content.startswith(b"\x89PNG")


def test_api_detects_lt_log_metadata_and_returns_scoped_tools(tmp_path):
    state = AppState(tmp_path)
    state.agent = AgentRuntime(
        state.repository,
        registry=state.tool_registry,
        llm=DeterministicLLMProvider(),
        generated_root=str(state.generated_root),
        plugin_registry=state.plugin_registry,
        calibration_registry=state.calibration_registry,
        metric_repository=state.metric_repository,
        task_queue=state.task_queue,
    )
    app = create_app(state)
    client = TestClient(app)
    case = client.post("/api/cases", json={"title": "LT offline", "equipment_type": "LT"}).json()

    upload = client.post(
        f"/api/cases/{case['id']}/files",
        files={"file": ("demo_LT-C.log", "example", "text/plain")},
    )
    snapshot = client.get(f"/api/cases/{case['id']}")
    tools = client.get(f"/api/tools?case_id={case['id']}&content=offline%20check")

    assert upload.status_code == 200
    assert upload.json()["log_kind"] == "LT-C"
    assert upload.json()["scenario"] == "offline_setup"
    assert snapshot.json()["datasets"][0]["matched_rule"] == "filename:LT-C"
    tool_names = {item["name"] for item in tools.json()["tools"]}
    assert "lt_list_log_pool" in tool_names
    assert "lt_example_offline_analyze" in tool_names


def test_api_streams_agent_events(tmp_path):
    state = AppState(tmp_path)
    state.agent = AgentRuntime(
        state.repository,
        registry=state.tool_registry,
        llm=DeterministicLLMProvider(),
        generated_root=str(state.generated_root),
        plugin_registry=state.plugin_registry,
        calibration_registry=state.calibration_registry,
        task_queue=state.task_queue,
    )
    app = create_app(state)
    client = TestClient(app)
    created = client.post("/api/cases", json={"title": "Streaming"}).json()
    case_id = created["id"]
    upload = client.post(
        f"/api/cases/{case_id}/files",
        files={"file": ("performance.csv", CSV_CONTENT, "text/csv")},
    )
    dataset_id = upload.json()["id"]

    with client.stream(
        "POST",
        f"/api/cases/{case_id}/messages/stream",
        json={"content": "请分析并诊断", "dataset_id": dataset_id},
    ) as response:
        body = response.read().decode()

    assert response.status_code == 200
    events = parse_sse_events(body)
    names = [event for event, _ in events]
    assert names[0] == "started"
    assert "route" in names
    assert "tool_start" in names
    assert "tool_result" in names
    assert "artifact_created" in names
    assert "message_delta" in names
    assert names[-1] == "final"
    final = events[-1][1]
    assert final["message"]["role"] == "assistant"
    assert any(item["kind"] == "diagnosis" for item in final["artifacts"])


def test_api_lists_tool_contracts(tmp_path):
    state = AppState(tmp_path)
    state.agent = AgentRuntime(
        state.repository,
        registry=state.tool_registry,
        llm=DeterministicLLMProvider(),
        generated_root=str(state.generated_root),
        plugin_registry=state.plugin_registry,
        calibration_registry=state.calibration_registry,
        task_queue=state.task_queue,
    )
    app = create_app(state)
    client = TestClient(app)

    case = client.post("/api/cases", json={"title": "Tool scope"}).json()
    client.post(
        f"/api/cases/{case['id']}/files",
        files={"file": ("performance.csv", CSV_CONTENT, "text/csv")},
    )
    default_response = client.get("/api/tools")
    response = client.get(f"/api/tools?case_id={case['id']}&content=请诊断")

    assert default_response.status_code == 200
    assert "parse_dataset" not in {tool["name"] for tool in default_response.json()["tools"]}
    assert response.status_code == 200
    names = {tool["name"] for tool in response.json()["tools"]}
    assert {"parse_dataset", "profile_dataset", "diagnose_performance", "generate_report"} <= names


def test_api_lists_diagnostic_plugins(tmp_path):
    state = AppState(tmp_path)
    app = create_app(state)
    client = TestClient(app)

    response = client.get("/api/plugins")

    assert response.status_code == 200
    plugin_types = {plugin["equipment_type"] for plugin in response.json()["plugins"]}
    assert {"generic_semiconductor_tool", "LT"} <= plugin_types


def test_api_generates_downloadable_ppt_report(tmp_path):
    state = AppState(tmp_path)
    state.agent = AgentRuntime(
        state.repository,
        registry=state.tool_registry,
        llm=DeterministicLLMProvider(),
        generated_root=str(state.generated_root),
        plugin_registry=state.plugin_registry,
        calibration_registry=state.calibration_registry,
        task_queue=state.task_queue,
    )
    app = create_app(state)
    client = TestClient(app)
    case = client.post("/api/cases", json={"title": "Report deck"}).json()
    upload = client.post(
        f"/api/cases/{case['id']}/files",
        files={"file": ("performance.csv", CSV_CONTENT, "text/csv")},
    )
    dataset_id = upload.json()["id"]

    response = client.post(
        f"/api/cases/{case['id']}/messages",
        json={"content": "请生成诊断报告", "dataset_id": dataset_id},
    )

    assert response.status_code == 200
    wait_for_tasks(state)
    snapshot = client.get(f"/api/cases/{case['id']}").json()
    reports = [item for item in snapshot["artifacts"] if item["kind"] == "report"]
    assert reports
    report = reports[-1]
    assert report["data"]["format"] == "pptx"
    assert report["data"]["template_engine"] == "ppt_template_sdk"
    ppt = client.get(f"/api/artifacts/{report['id']}/file")
    assert ppt.status_code == 200
    assert ppt.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    )
    assert ppt.content.startswith(b"PK")


def test_api_creates_and_runs_workflow_from_case(tmp_path):
    state = AppState(tmp_path)
    state.agent = AgentRuntime(
        state.repository,
        registry=state.tool_registry,
        llm=DeterministicLLMProvider(),
        generated_root=str(state.generated_root),
        plugin_registry=state.plugin_registry,
        calibration_registry=state.calibration_registry,
        metric_repository=state.metric_repository,
        task_queue=state.task_queue,
    )
    app = create_app(state)
    client = TestClient(app)
    case = client.post("/api/cases", json={"title": "Workflow case"}).json()
    upload = client.post(
        f"/api/cases/{case['id']}/files",
        files={"file": ("performance.csv", CSV_CONTENT, "text/csv")},
    )
    dataset_id = upload.json()["id"]
    response = client.post(
        f"/api/cases/{case['id']}/messages",
        json={"content": "请分析并诊断", "dataset_id": dataset_id},
    )
    assert response.status_code == 200

    created = client.post(
        f"/api/cases/{case['id']}/workflows",
        json={"name": "Replay diagnostic", "description": "Replay the successful tool sequence."},
    )
    workflows = client.get("/api/workflows")
    replay = client.post(f"/api/cases/{case['id']}/workflows/{created.json()['id']}/run")

    assert created.status_code == 200
    assert workflows.status_code == 200
    assert workflows.json()["workflows"][0]["name"] == "Replay diagnostic"
    assert replay.status_code == 200
    assert any(item["tool_name"] == "diagnose_performance" for item in replay.json()["results"])


def test_trace_api_returns_debug_data_with_redaction(tmp_path):
    state = AppState(tmp_path)
    app = create_app(state)
    client = TestClient(app)
    case = state.repository.create_case("Trace debug")
    state.repository.add_agent_step_trace(
        AgentStepTrace(
            case_id=case.id,
            step_index=1,
            phase="observe",
            observations=[{"summary": "ok"}],
            llm_metadata={"tool_mode": "prompt_xml_json", "api_key": "step-secret"},
        )
    )
    state.repository.add_llm_audit_event(
        LLMAuditEvent(
            case_id=case.id,
            provider="openai_compatible",
            model="mock",
            request={
                "headers": {"Authorization": "Bearer secret-token"},
                "api_key": "secret-key",
                "messages": [{"role": "user", "content": "x"}],
            },
            response={"choices": [{"message": {"content": "ok"}}]},
            duration_ms=12,
        )
    )
    state.repository.add_llm_audit_event(
        LLMAuditEvent(
            case_id=case.id,
            provider="openai_compatible",
            model="mock",
            request={"messages": [{"role": "user", "content": "stream"}]},
            response={
                "stream": True,
                "chunks": [
                    {"choices": [{"delta": {"content": "诊断"}, "finish_reason": None}]},
                    {"choices": [{"delta": {"content": "完成"}, "finish_reason": "stop"}]},
                ],
            },
            duration_ms=14,
        )
    )

    response = client.get(f"/api/cases/{case.id}/trace")

    assert response.status_code == 200
    body = response.json()
    assert body["agent_steps"][0]["phase"] == "observe"
    assert body["llm_audit_events"][0]["response_summary"]["content"] == "ok"
    assert body["llm_audit_events"][1]["response_summary"]["content"] == "诊断完成"
    assert body["llm_audit_events"][1]["response_summary"]["chunk_count"] == 2
    dumped = response.text
    assert "secret-token" not in dumped
    assert "secret-key" not in dumped
    assert "step-secret" not in dumped
    assert "***" in dumped

    export = client.get(f"/api/cases/{case.id}/trace/export")
    assert export.status_code == 200
    assert export.headers["content-type"].startswith("application/json")
    assert "secret-token" not in export.text
