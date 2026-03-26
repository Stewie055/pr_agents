from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel, Field, ValidationError

from pr_agents.agent.intents import IntentParser, LLMProvider
from pr_agents.models import AgentAction, AgentEntry, AgentIntent


class PlannedStep(BaseModel):
    step_index: int
    title: str
    tool_name: str
    inputs_summary: dict = Field(default_factory=dict)


class ExecutionPlan(BaseModel):
    goal: str
    steps: list[PlannedStep]
    planner_source: str
    used_fallback: bool = False


class ConversationRouter:
    def route(self, content: str) -> AgentAction | None:
        normalized = content.strip()
        lower = normalized.lower()
        if not normalized:
            return AgentAction.CHAT
        if self._is_chat(lower, normalized):
            return AgentAction.CHAT
        if self._is_report_follow_up(lower, normalized):
            return AgentAction.SHOW_REPORT
        if self._looks_like_task(lower, normalized):
            return None
        return AgentAction.CHAT

    def is_explicit_task(self, content: str) -> bool:
        normalized = content.strip()
        lower = normalized.lower()
        has_business = "a_demo" in lower or "b001" in lower or "A_DEMO" in normalized or "B001" in normalized
        has_intent = any(
            marker in lower or marker in normalized
            for marker in ("scientific plot", "report", "chart", "plot", "分析", "报告", "画图", "绘图", "database", "数据库")
        )
        return has_business and has_intent

    @staticmethod
    def _is_chat(lower: str, original: str) -> bool:
        chat_phrases = {
            "hi",
            "hello",
            "hey",
            "你好",
            "您好",
            "嗨",
            "在吗",
            "你是谁",
            "你能做什么",
            "怎么用",
            "help",
        }
        return lower in chat_phrases or original in chat_phrases

    @staticmethod
    def _is_report_follow_up(lower: str, original: str) -> bool:
        return (
            "show me the report again" in lower
            or "show the report again" in lower
            or "report again" in lower
            or "show latest report" in lower
            or "summarize the report" in lower
            or "summarise the report" in lower
            or "report summary" in lower
            or "key points" in lower
            or "再看报告" in original
            or "重新看报告" in original
            or "概括这份报告" in original
            or "总结这份报告" in original
            or "报告重点" in original
        )

    @staticmethod
    def _looks_like_task(lower: str, original: str) -> bool:
        markers = (
            "a_demo",
            "b001",
            "database",
            "scientific plot",
            "report",
            "analy",
            "chart",
            "plot",
            "分析",
            "报告",
            "画图",
            "绘图",
            "数据库",
        )
        return any(marker in lower or marker in original for marker in markers)


class Planner(Protocol):
    mode: str

    def build_plan(self, intent: AgentIntent) -> ExecutionPlan:
        ...


class FakePlanner:
    mode = "fake"

    def build_plan(self, intent: AgentIntent) -> ExecutionPlan:
        if intent.entry == AgentEntry.DATABASE:
            first = PlannedStep(
                step_index=0,
                title=f"Run database analysis workflow for {intent.business_code}",
                tool_name="run_db_analysis_workflow",
                inputs_summary={
                    "business_code": intent.business_code,
                    "entry": intent.entry.value,
                    "chart_type": intent.chart_type,
                },
            )
        else:
            first = PlannedStep(
                step_index=0,
                title=f"Run file analysis workflow for {intent.business_code}",
                tool_name="run_file_analysis_workflow",
                inputs_summary={
                    "business_code": intent.business_code,
                    "entry": intent.entry.value,
                    "chart_type": intent.chart_type,
                },
            )

        second = PlannedStep(
            step_index=1,
            title="Summarize workflow results for the user",
            tool_name="summarize_session_results",
            inputs_summary={"goal": intent.objective},
        )
        return ExecutionPlan(
            goal=intent.objective,
            steps=[first, second],
            planner_source=self.mode,
            used_fallback=False,
        )


class LLMPlanner:
    mode = "llm"

    def __init__(self, provider: LLMProvider, model: str | None, timeout: float, fallback_planner: Planner) -> None:
        self.provider = provider
        self.model = model or ""
        self.timeout = timeout
        self.fallback_planner = fallback_planner

    def build_plan(self, intent: AgentIntent) -> ExecutionPlan:
        try:
            if not self.provider.is_configured() or not self.model:
                raise ValueError("llm planner is not configured")
            raw = self.provider.complete_json(
                system_prompt=self._system_prompt(),
                user_prompt=intent.model_dump_json(),
                model=self.model,
                timeout=self.timeout,
            )
            plan = ExecutionPlan.model_validate(self._extract_json(raw))
            plan.planner_source = self.mode
            plan.used_fallback = False
            return plan
        except (ValueError, KeyError, ValidationError, json.JSONDecodeError):
            fallback = self.fallback_planner.build_plan(intent)
            fallback.planner_source = f"{self.mode}_fallback"
            fallback.used_fallback = True
            return fallback

    @staticmethod
    def _system_prompt() -> str:
        return (
            "Return valid JSON only with fields goal, steps, planner_source, used_fallback. "
            "Each step must include step_index, title, tool_name, inputs_summary. "
            "Allowed tool_name values: run_file_analysis_workflow, run_db_analysis_workflow, summarize_session_results. "
            "Create exactly two steps: the workflow execution step matching the entry, then summarize_session_results."
        )

    @staticmethod
    def _extract_json(content: str) -> dict:
        stripped = content.strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            stripped = "\n".join(line for line in lines if not line.startswith("```")).strip()
        return json.loads(stripped)


@dataclass
class AgentRuntimeDependencies:
    router: ConversationRouter
    intent_parser: IntentParser
    planner: Planner
