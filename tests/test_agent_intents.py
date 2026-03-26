import json

from pr_agents.agent.intents import FakeIntentParser, GLMProvider, LLMIntentParser
from pr_agents.agent.runtime import ConversationRouter, FakePlanner
from pr_agents.models import AgentAction, AgentEntry, IntentMode, SourcePattern


def test_intent_parser_recognizes_database_request() -> None:
    parser = FakeIntentParser()

    intent = parser.parse("Please use A_DEMO database data to generate a scientific plot and report.")

    assert intent.action == AgentAction.ANALYZE
    assert intent.entry == AgentEntry.DATABASE
    assert intent.business_code == "A_DEMO"
    assert intent.chart_type == "scientific_plot"
    assert intent.intent_source == IntentMode.FAKE.value


def test_intent_parser_recognizes_chat_message() -> None:
    parser = FakeIntentParser()

    intent = parser.parse("你好")

    assert intent.action == AgentAction.CHAT
    assert intent.intent_source == IntentMode.FAKE.value


def test_intent_parser_recognizes_report_follow_up() -> None:
    parser = FakeIntentParser()

    intent = parser.parse("Show me the report again.")

    assert intent.action == AgentAction.SHOW_REPORT
    assert intent.entry == AgentEntry.FILE
    assert intent.source_pattern == SourcePattern.PER_BUSINESS_FILE


def test_intent_parser_recognizes_report_summary_follow_up() -> None:
    parser = FakeIntentParser()

    intent = parser.parse("Please summarize the report key points.")

    assert intent.action == AgentAction.SHOW_REPORT


def test_llm_intent_parser_returns_llm_intent() -> None:
    captured: dict[str, object] = {}

    def requester(url: str, payload: dict[str, object], headers: dict[str, str], timeout: float) -> str:
        captured["url"] = url
        captured["payload"] = payload
        captured["headers"] = headers
        captured["timeout"] = timeout
        return json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"action":"analyze","business_code":"A_DEMO","entry":"file",'
                                '"objective":"Please analyze A_DEMO.","chart_type":"scientific_plot",'
                                '"source_pattern":"per_business_file"}'
                            )
                        }
                    }
                ]
            }
        )

    parser = LLMIntentParser(
        provider=GLMProvider(
            base_url="https://glm.example.com/v1",
            api_key="secret",
            requester=requester,
        ),
        model="demo-model",
    )

    intent = parser.parse("Please analyze A_DEMO.")

    assert captured["url"] == "https://glm.example.com/v1/chat/completions"
    assert captured["payload"]["model"] == "demo-model"
    assert captured["headers"]["Authorization"] == "Bearer secret"
    assert captured["timeout"] == 30.0
    assert intent.intent_source == IntentMode.LLM.value
    assert intent.used_fallback is False
    assert intent.business_code == "A_DEMO"


def test_llm_intent_parser_falls_back_to_fake() -> None:
    parser = LLMIntentParser(
        provider=GLMProvider(
            base_url="https://glm.example.com/v1",
            api_key="secret",
            requester=lambda _url, _payload, _headers, _timeout: "not json",
        ),
        model="demo-model",
        fallback_parser=FakeIntentParser(),
    )

    intent = parser.parse("Please use A_DEMO database data to generate a report.")

    assert intent.intent_source == "llm_fallback"
    assert intent.used_fallback is True
    assert intent.entry == AgentEntry.DATABASE


def test_llm_intent_parser_falls_back_when_provider_is_not_configured() -> None:
    parser = LLMIntentParser(
        provider=GLMProvider(base_url="", api_key=""),
        model="GLM-4.5-Air",
        fallback_parser=FakeIntentParser(),
    )

    intent = parser.parse("Please analyze A_DEMO from the database.")

    assert intent.intent_source == "llm_fallback"
    assert intent.used_fallback is True
    assert intent.entry == AgentEntry.DATABASE


def test_conversation_router_fast_paths_chat_and_report() -> None:
    router = ConversationRouter()

    assert router.route("你好") == AgentAction.CHAT
    assert router.route("Show me the report again.") == AgentAction.SHOW_REPORT
    assert router.route("Please summarize the report key points.") == AgentAction.SHOW_REPORT
    assert router.route("Please use A_DEMO file data to generate a scientific plot and report.") is None


def test_fake_planner_builds_two_step_workflow_plan() -> None:
    planner = FakePlanner()
    intent = FakeIntentParser().parse("Please use A_DEMO database data to generate a scientific plot and report.")

    plan = planner.build_plan(intent)

    assert len(plan.steps) == 2
    assert plan.steps[0].tool_name == "run_db_analysis_workflow"
    assert plan.steps[1].tool_name == "summarize_session_results"
