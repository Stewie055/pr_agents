from __future__ import annotations

from pr_agents.models import AgentAction, AgentEntry, AgentIntent, SourcePattern


class AgentIntentParser:
    """A small, explicit intent layer between chat input and task execution."""

    def parse(self, content: str) -> AgentIntent:
        normalized = content.strip()
        upper = normalized.upper()
        lower = normalized.lower()

        if self._is_report_follow_up(normalized):
            return AgentIntent(
                action=AgentAction.SHOW_REPORT,
                business_code=self._extract_business_code(upper),
                entry=self._detect_entry(lower),
                objective=normalized or "Show the latest report",
                chart_type=self._detect_chart_type(lower),
                source_pattern=self._detect_source_pattern(upper),
            )

        return AgentIntent(
            action=AgentAction.ANALYZE,
            business_code=self._extract_business_code(upper),
            entry=self._detect_entry(lower),
            objective=normalized or "Generate a scientific plot report",
            chart_type=self._detect_chart_type(lower),
            source_pattern=self._detect_source_pattern(upper),
        )

    @staticmethod
    def _extract_business_code(upper: str) -> str:
        if "A_DEMO" in upper:
            return "A_DEMO"
        if "B001" in upper:
            return "B001"
        return "A_DEMO"

    @staticmethod
    def _detect_entry(lower: str) -> AgentEntry:
        if "database" in lower or "数据库" in lower:
            return AgentEntry.DATABASE
        return AgentEntry.FILE

    @staticmethod
    def _detect_chart_type(lower: str) -> str:
        if "scientific" in lower or "科学绘图" in lower:
            return "scientific_plot"
        return "scientific_plot"

    @staticmethod
    def _detect_source_pattern(upper: str) -> SourcePattern:
        if "B001" in upper:
            return SourcePattern.SHARED_FILE
        return SourcePattern.PER_BUSINESS_FILE

    @staticmethod
    def _is_report_follow_up(content: str) -> bool:
        lower = content.lower()
        return (
            "show me the report again" in lower
            or "show the report again" in lower
            or "report again" in lower
            or "show latest report" in lower
            or "再看报告" in content
            or "重新看报告" in content
        )
