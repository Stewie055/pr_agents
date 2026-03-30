import asyncio
from pathlib import Path

from pr_agents.bootstrap import build_components
from pr_agents.models import AgentUserMessageRequest, IntentMode
from pr_agents.settings import Settings


def build_test_settings(tmp_path: Path) -> Settings:
    return Settings(
        artifact_base_dir=str(tmp_path / "artifacts"),
        sqlite_path=str(tmp_path / "artifacts" / "app.db"),
        intent_mode=IntentMode.FAKE,
    )


def test_react_agent_workspace_demo_flow(tmp_path: Path) -> None:
    _, agent_session_service = build_components(build_test_settings(tmp_path))
    session_id = agent_session_service.create_session().session_id
    source = agent_session_service.register_demo_source(session_id, "a_demo_file")
    start = agent_session_service.start_message_run(
        session_id,
        AgentUserMessageRequest(
            content="Please use A_DEMO file data to generate a scientific plot and report.",
            source_id=source.source_id,
        ),
    )

    async def collect():
        return [event async for event in agent_session_service.stream_run_events(session_id, start.run_id)]

    events = asyncio.run(collect())

    assert any(event.event == "tool_called" for event in events)
    payload = agent_session_service.get_session(session_id)
    assert payload.sources
    assert payload.runs
    assert payload.tasks
