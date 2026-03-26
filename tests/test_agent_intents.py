import asyncio
from pathlib import Path

from pydantic_ai.models.function import FunctionModel
from pydantic_ai.models.openai import OpenAIModel

from pr_agents.agent.llm import FakeLLM, GLMProvider, build_agent_model
from pr_agents.agent.memory import MemoryManager
from pr_agents.bootstrap import build_components
from pr_agents.models import AgentUserMessageRequest, IntentMode
from pr_agents.settings import Settings


def build_test_settings(tmp_path: Path) -> Settings:
    return Settings(
        artifact_base_dir=str(tmp_path / "artifacts"),
        sqlite_path=str(tmp_path / "artifacts" / "app.db"),
        intent_mode=IntentMode.FAKE,
    )


def test_fake_llm_builds_function_model() -> None:
    model = FakeLLM().build_model()
    assert isinstance(model, FunctionModel)


def test_glm_provider_builds_openai_compatible_model() -> None:
    provider = GLMProvider(base_url="https://glm.example.com/v1", api_key="secret")
    model = provider.build_model("glm-4.5-air")
    assert isinstance(model, OpenAIModel)
    assert model.model_name == "glm-4.5-air"


def test_build_agent_model_uses_fake_when_llm_not_configured(tmp_path: Path) -> None:
    settings = Settings(
        artifact_base_dir=str(tmp_path / "artifacts"),
        sqlite_path=str(tmp_path / "artifacts" / "app.db"),
        intent_mode=IntentMode.LLM,
        llm_base_url="",
        llm_api_key="",
    )
    model, mode = build_agent_model(settings)
    assert isinstance(model, FunctionModel)
    assert mode == IntentMode.FAKE.value


def test_memory_manager_collects_latest_report_summary(tmp_path: Path) -> None:
    settings = build_test_settings(tmp_path)
    _, task_service, agent_session_service = build_components(settings)
    session_id = agent_session_service.create_session().session_id
    start = agent_session_service.start_message_run(
        session_id,
        AgentUserMessageRequest(content="Please use A_DEMO file data to generate a scientific plot and report."),
    )

    async def collect():
        return [event async for event in agent_session_service.stream_run_events(session_id, start.run_id)]

    asyncio.run(collect())
    memory = MemoryManager(agent_session_service.session_repository, task_service).snapshot(session_id)

    assert memory.mid_term.latest_task_summary["business_code"] == "A_DEMO"
    assert memory.mid_term.latest_report_summary.startswith("Analysis completed")


def test_agent_runtime_executes_database_demo_flow(tmp_path: Path) -> None:
    settings = build_test_settings(tmp_path)
    _, _, agent_session_service = build_components(settings)
    session_id = agent_session_service.create_session().session_id
    start = agent_session_service.start_message_run(
        session_id,
        AgentUserMessageRequest(content="Please use database data to generate a scientific plot and report for A_DEMO."),
    )

    async def collect():
        return [event async for event in agent_session_service.stream_run_events(session_id, start.run_id)]

    events = asyncio.run(collect())
    event_names = [event.event for event in events]

    assert "tool_called" in event_names
    assert "assistant_delta" in event_names
    assert "run_completed" in event_names
