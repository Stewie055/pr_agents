from pr_agents.agent.intents import AgentIntentParser
from pr_agents.models import AgentAction, AgentEntry, SourcePattern


def test_intent_parser_recognizes_database_request() -> None:
    parser = AgentIntentParser()

    intent = parser.parse("Please use A_DEMO database data to generate a scientific plot and report.")

    assert intent.action == AgentAction.ANALYZE
    assert intent.entry == AgentEntry.DATABASE
    assert intent.business_code == "A_DEMO"
    assert intent.chart_type == "scientific_plot"


def test_intent_parser_recognizes_report_follow_up() -> None:
    parser = AgentIntentParser()

    intent = parser.parse("Show me the report again.")

    assert intent.action == AgentAction.SHOW_REPORT
    assert intent.entry == AgentEntry.FILE
    assert intent.source_pattern == SourcePattern.PER_BUSINESS_FILE
