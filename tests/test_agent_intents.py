import json
from pathlib import Path

from pr_agents.agent.context import ContextManager
from pr_agents.agent.factory import build_agent_runtime
from pr_agents.agent.llm import FakeLLM, GLMProvider
from pr_agents.agent.memory import MemoryManager
from pr_agents.agent.planner_agent import PlannerAgent
from pr_agents.agent.react_agent import ReactAgent
from pr_agents.bootstrap import build_components
from pr_agents.models import AgentContext, AgentDecisionAction, AgentEntry, AgentUserMessageRequest, IntentMode
from pr_agents.settings import Settings


def build_test_settings(tmp_path: Path) -> Settings:
    return Settings(
        artifact_base_dir=str(tmp_path / "artifacts"),
        sqlite_path=str(tmp_path / "artifacts" / "app.db"),
        intent_mode=IntentMode.FAKE,
    )


def test_fake_llm_returns_database_workflow_decision() -> None:
    llm = FakeLLM()

    payload = json.loads(
        llm.complete_json(
            system_prompt="AGENT_DECISION",
            user_prompt="Please use A_DEMO database data to generate a scientific plot and report.",
            model="fake",
            timeout=30.0,
        )
    )

    assert payload["action"] == AgentDecisionAction.CALL_TOOL.value
    assert payload["tool_name"] == "run_db_analysis_workflow"
    assert payload["tool_input"]["entry"] == AgentEntry.DATABASE.value


def test_fake_llm_returns_report_summary_tool_decision() -> None:
    llm = FakeLLM()

    payload = json.loads(
        llm.complete_json(
            system_prompt="AGENT_DECISION",
            user_prompt="Please summarize the report key points.",
            model="fake",
            timeout=30.0,
        )
    )

    assert payload["action"] == AgentDecisionAction.CALL_TOOL.value
    assert payload["tool_name"] == "summarize_report"


def test_glm_provider_constructs_request() -> None:
    captured: dict[str, object] = {}

    def requester(url: str, payload: dict[str, object], headers: dict[str, str], timeout: float) -> str:
        captured["url"] = url
        captured["payload"] = payload
        captured["headers"] = headers
        captured["timeout"] = timeout
        return json.dumps({"choices": [{"message": {"content": '{"ok": true}'}}]})

    provider = GLMProvider(
        base_url="https://glm.example.com/v1",
        api_key="secret",
        requester=requester,
    )

    response = provider.complete_json(
        system_prompt="system",
        user_prompt="user",
        model="demo-model",
        timeout=30.0,
    )

    assert captured["url"] == "https://glm.example.com/v1/chat/completions"
    assert captured["payload"]["model"] == "demo-model"
    assert captured["headers"]["Authorization"] == "Bearer secret"
    assert response == '{"ok": true}'


def test_react_agent_falls_back_to_fake_llm() -> None:
    react_agent = ReactAgent(
        llm=GLMProvider(
            base_url="https://glm.example.com/v1",
            api_key="secret",
            requester=lambda _url, _payload, _headers, _timeout: "not json",
        ),
        model_name="demo-model",
        timeout=30.0,
        fallback_llm=FakeLLM(),
        mode=IntentMode.LLM.value,
        allowed_tools={
            "run_file_analysis_workflow",
            "run_db_analysis_workflow",
            "load_latest_report",
            "summarize_report",
        },
    )

    decision = react_agent.decide(
        AgentContext(session_id="session-1", user_message="Please use A_DEMO file data to generate a scientific plot and report.")
    )

    assert decision.decision_source == "llm_fallback"


def test_planner_agent_builds_two_step_database_plan() -> None:
    planner = PlannerAgent(
        llm=FakeLLM(),
        model_name="fake",
        timeout=30.0,
        fallback_llm=FakeLLM(),
        mode=IntentMode.FAKE.value,
    )
    decision = {
        "tool_name": "run_db_analysis_workflow",
        "tool_input": {
            "business_code": "A_DEMO",
            "entry": AgentEntry.DATABASE.value,
            "objective": "Please use database data to generate a scientific plot and report for A_DEMO.",
            "chart_type": "scientific_plot",
        },
    }

    plan = planner.build_plan(
        AgentContext(session_id="session-1", user_message=decision["tool_input"]["objective"]),
        decision,
    )

    assert len(plan.steps) == 2
    assert plan.steps[0].tool_name == "run_db_analysis_workflow"
    assert plan.steps[1].tool_name == "summarize_session_results"


def test_memory_manager_collects_latest_report_summary(tmp_path: Path) -> None:
    settings = build_test_settings(tmp_path)
    _, task_service, agent_session_service = build_components(settings)
    session_id = agent_session_service.create_session().session_id
    start = agent_session_service.start_message_run(
        session_id,
        AgentUserMessageRequest(content="Please use A_DEMO file data to generate a scientific plot and report."),
    )
    list(agent_session_service.stream_run_events(session_id, start.run_id))

    memory = MemoryManager(agent_session_service.session_repository, task_service).snapshot(session_id)

    assert memory.mid_term.latest_task_summary["business_code"] == "A_DEMO"
    assert memory.mid_term.latest_report_summary.startswith("Analysis completed")


def test_agent_runtime_executes_database_demo_flow(tmp_path: Path) -> None:
    settings = build_test_settings(tmp_path)
    _, task_service, agent_session_service = build_components(settings)
    session_id = agent_session_service.create_session().session_id
    start = agent_session_service.start_message_run(
        session_id,
        AgentUserMessageRequest(content="Please use database data to generate a scientific plot and report for A_DEMO."),
    )

    events = list(agent_session_service.stream_run_events(session_id, start.run_id))

    assert any(event.event == "plan_created" for event in events)
    assert any(event.event == "tool_called" for event in events)
    assert any(event.event == "run_completed" for event in events)
