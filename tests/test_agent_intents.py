import json

from pr_agents.agent.intents import FakeIntentParser, GLMProvider, LLMIntentParser
from pr_agents.models import AgentAction, AgentEntry, IntentMode, SourcePattern


def test_intent_parser_recognizes_database_request() -> None:
    parser = FakeIntentParser()

    intent = parser.parse("Please use A_DEMO database data to generate a scientific plot and report.")

    assert intent.action == AgentAction.ANALYZE
    assert intent.entry == AgentEntry.DATABASE
    assert intent.business_code == "A_DEMO"
    assert intent.chart_type == "scientific_plot"
    assert intent.intent_source == IntentMode.FAKE.value


def test_intent_parser_recognizes_report_follow_up() -> None:
    parser = FakeIntentParser()

    intent = parser.parse("Show me the report again.")

    assert intent.action == AgentAction.SHOW_REPORT
    assert intent.entry == AgentEntry.FILE
    assert intent.source_pattern == SourcePattern.PER_BUSINESS_FILE


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
