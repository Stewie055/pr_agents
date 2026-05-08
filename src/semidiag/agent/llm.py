from __future__ import annotations


class StubLLMProvider:
    """Deterministic provider used to validate orchestration without a real LLM."""

    def plan_tools(self, message: str, has_dataset: bool) -> list[str]:
        normalized = message.lower()
        if not has_dataset:
            return []
        if any(word in normalized for word in ["report", "报告"]):
            return ["parse_dataset", "profile_dataset", "build_trend_chart", "diagnose_performance", "generate_report"]
        if any(word in normalized for word in ["diagnose", "诊断", "异常", "建议", "analyze", "分析"]):
            return ["parse_dataset", "profile_dataset", "build_trend_chart", "diagnose_performance"]
        return ["parse_dataset", "profile_dataset"]
