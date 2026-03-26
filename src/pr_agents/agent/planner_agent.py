from __future__ import annotations

import json

from pydantic import ValidationError

from pr_agents.models import AgentContext, AgentEntry, AgentPlan

from .llm import AgentLLM


class PlannerAgent:
    def __init__(
        self,
        llm: AgentLLM,
        model_name: str,
        timeout: float,
        fallback_llm: AgentLLM,
        mode: str,
    ) -> None:
        self.llm = llm
        self.model_name = model_name
        self.timeout = timeout
        self.fallback_llm = fallback_llm
        self.mode = mode

    def build_plan(self, context: AgentContext, decision: dict) -> AgentPlan:
        user_prompt = json.dumps(
            {
                "user_message": context.user_message,
                "latest_report_summary": context.latest_report_summary,
                "decision": decision,
            },
            ensure_ascii=False,
        )
        try:
            raw = self.llm.complete_json(
                system_prompt=self._system_prompt(),
                user_prompt=user_prompt,
                model=self.model_name,
                timeout=self.timeout,
            )
            payload = self._extract_json(raw)
            self._normalize_payload(payload, decision, context.user_message)
            plan = AgentPlan.model_validate(payload)
            plan.planner_source = self.mode
            plan.used_fallback = False
            return plan
        except (ValueError, KeyError, ValidationError, json.JSONDecodeError):
            raw = self.fallback_llm.complete_json(
                system_prompt=self._system_prompt(),
                user_prompt=user_prompt,
                model="fake",
                timeout=self.timeout,
            )
            payload = self._extract_json(raw)
            self._normalize_payload(payload, decision, context.user_message)
            plan = AgentPlan.model_validate(payload)
            plan.planner_source = f"{self.mode}_fallback"
            plan.used_fallback = True
            return plan

    @staticmethod
    def _system_prompt() -> str:
        return (
            "AGENT_PLAN: Return valid JSON only with fields goal, business_code, entry, steps, "
            "expected_outputs, planner_source, used_fallback. "
            "Allowed tool_name values: run_file_analysis_workflow, run_db_analysis_workflow, summarize_session_results. "
            "Create exactly two steps: the workflow execution step matching the requested entry, then summarize_session_results."
        )

    @staticmethod
    def _extract_json(content: str) -> dict:
        stripped = content.strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            stripped = "\n".join(line for line in lines if not line.startswith("```")).strip()
        payload = json.loads(stripped)
        if isinstance(payload.get("entry"), str):
            payload["entry"] = AgentEntry(payload["entry"])
        return payload

    @staticmethod
    def _normalize_payload(payload: dict, decision: dict, user_message: str) -> None:
        tool_input = decision.get("tool_input", {})
        payload.setdefault("goal", tool_input.get("objective", user_message))
        payload.setdefault("business_code", tool_input.get("business_code", "A_DEMO"))
        payload.setdefault("entry", tool_input.get("entry", AgentEntry.FILE.value))
        expected = payload.get("expected_outputs")
        if isinstance(expected, str):
            payload["expected_outputs"] = ["chart", "report"]
        steps = payload.get("steps", [])
        normalized_steps = []
        for index, step in enumerate(steps):
            tool_name = step.get("tool_name")
            title = step.get("title")
            params = step.get("inputs_summary") or step.get("parameters") or {}
            if not title:
                if tool_name == "run_db_analysis_workflow":
                    title = f"Run database analysis workflow for {payload['business_code']}"
                elif tool_name == "run_file_analysis_workflow":
                    title = f"Run file analysis workflow for {payload['business_code']}"
                else:
                    title = "Summarize workflow results for the user"
            normalized_steps.append(
                {
                    "step_index": step.get("step_index", index),
                    "title": title,
                    "tool_name": tool_name,
                    "inputs_summary": params,
                }
            )
        if normalized_steps:
            payload["steps"] = normalized_steps
