from __future__ import annotations

import json

from pydantic import ValidationError

from pr_agents.models import AgentContext, AgentDecision, AgentDecisionAction

from .llm import AgentLLM


class ReactAgent:
    def __init__(
        self,
        llm: AgentLLM,
        model_name: str,
        timeout: float,
        fallback_llm: AgentLLM,
        mode: str,
        allowed_tools: set[str],
    ) -> None:
        self.llm = llm
        self.model_name = model_name
        self.timeout = timeout
        self.fallback_llm = fallback_llm
        self.mode = mode
        self.allowed_tools = allowed_tools

    def decide(self, context: AgentContext) -> AgentDecision:
        user_prompt = json.dumps(
            {
                "user_message": context.user_message,
                "recent_tasks": context.recent_tasks,
                "latest_report_summary": context.latest_report_summary,
                "has_latest_report": bool(context.latest_report_artifact_id),
            },
            ensure_ascii=False,
        )
        try:
            raw = self.llm.complete_json(
                system_prompt=self._system_prompt(self.allowed_tools),
                user_prompt=user_prompt,
                model=self.model_name,
                timeout=self.timeout,
            )
            payload = self._extract_json(raw)
            self._normalize_payload(payload, context.user_message)
            decision = AgentDecision.model_validate(payload)
            decision.decision_source = self.mode
            decision.used_fallback = False
        except (ValueError, KeyError, ValidationError, json.JSONDecodeError):
            raw = self.fallback_llm.complete_json(
                system_prompt=self._system_prompt(self.allowed_tools),
                user_prompt=user_prompt,
                model="fake",
                timeout=self.timeout,
            )
            payload = self._extract_json(raw)
            self._normalize_payload(payload, context.user_message)
            decision = AgentDecision.model_validate(payload)
            decision.decision_source = f"{self.mode}_fallback"
            decision.used_fallback = True

        if decision.action == AgentDecisionAction.CALL_TOOL and decision.tool_name not in self.allowed_tools:
            return AgentDecision(
                action=AgentDecisionAction.RESPOND,
                response="I could not safely execute that tool request. Please try a supported demo workflow.",
                thought_summary="The requested tool is outside the allowed set.",
                decision_source=decision.decision_source,
                used_fallback=decision.used_fallback,
            )
        return decision

    @staticmethod
    def _system_prompt(allowed_tools: set[str]) -> str:
        return (
            "AGENT_DECISION: Return valid JSON only with fields action, tool_name, tool_input, response, thought_summary. "
            "Allowed action values: respond, call_tool, finish. "
            f"Allowed tool_name values: {', '.join(sorted(allowed_tools))}. "
            "Decide whether to reply directly or call one allowed tool. "
            "Use tools for report retrieval, report summarization, file analysis, or database analysis when needed."
        )

    @staticmethod
    def _extract_json(content: str) -> dict:
        stripped = content.strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            stripped = "\n".join(line for line in lines if not line.startswith("```")).strip()
        return json.loads(stripped)

    @staticmethod
    def _normalize_payload(payload: dict, user_message: str) -> None:
        tool_name = payload.get("tool_name")
        if payload.get("action") == AgentDecisionAction.CALL_TOOL.value and tool_name:
            tool_input = payload.setdefault("tool_input", {})
            if tool_name in {"run_file_analysis_workflow", "run_db_analysis_workflow"}:
                upper = user_message.upper()
                lower = user_message.lower()
                tool_input.setdefault("business_code", "B001" if "B001" in upper else "A_DEMO")
                tool_input.setdefault(
                    "entry",
                    "database" if tool_name == "run_db_analysis_workflow" or "database" in lower or "数据库" in user_message else "file",
                )
                tool_input.setdefault("objective", user_message)
                tool_input.setdefault("chart_type", "scientific_plot")
                tool_input.setdefault(
                    "source_pattern",
                    "shared_file" if tool_input.get("business_code") == "B001" else "per_business_file",
                )
