from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ValidationError

from semidiag.agent.llm import LLMError, LLMProvider

IntentName = Literal[
    "chat_response",
    "knowledge_qa",
    "data_analysis",
    "diagnosis",
    "report_generation",
    "workflow_request",
    "clarification",
]


class RouteDecision(BaseModel):
    intent: IntentName
    requires_dataset: bool = False
    requires_knowledge: bool = False
    target_workflow: str | None = None
    user_goal: str = ""
    response_style: Literal["brief", "normal", "detailed"] = "normal"
    reason: str = ""


@dataclass
class CaseRouteContext:
    has_dataset: bool
    dataset_count: int
    artifact_count: int
    evidence_count: int
    latest_dataset_filename: str | None = None


class LLMRouter:
    def __init__(self, llm: LLMProvider) -> None:
        self.llm = llm

    def route(self, *, user_content: str, context: CaseRouteContext) -> RouteDecision:
        messages = [
            {
                "role": "system",
                "content": (
                    "你是半导体设备诊断 Agent 的路由器。"
                    "只判断用户意图和后续路径，不执行分析，不输出给用户看的回答。"
                    "必须只输出 JSON，不要 Markdown，不要解释。"
                    "intent 只能是 chat_response, knowledge_qa, data_analysis, diagnosis, "
                    "report_generation, workflow_request, clarification。"
                    "如果用户只是寒暄或一般对话，intent=chat_response。"
                    "如果用户询问术语、手册、原理、资料、经验，intent=knowledge_qa。"
                    "如果用户要求统计、画像、趋势或比较，intent=data_analysis。"
                    "如果用户要求异常原因、故障、诊断、建议，intent=diagnosis。"
                    "如果用户要求生成报告，intent=report_generation。"
                    "如果用户要求保存流程、批处理、定时执行，intent=workflow_request。"
                    "分析、诊断、报告通常 requires_dataset=true；资料问答和寒暄不需要。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"用户输入: {user_content}\n"
                    f"当前状态: has_dataset={context.has_dataset}, "
                    f"dataset_count={context.dataset_count}, artifact_count={context.artifact_count}, "
                    f"evidence_count={context.evidence_count}, latest_dataset_filename={context.latest_dataset_filename or 'none'}\n"
                    "输出 JSON 字段: intent, requires_dataset, requires_knowledge, target_workflow, "
                    "user_goal, response_style, reason。"
                ),
            },
        ]
        result = self.llm.summarize_turn(messages=messages)
        return self._parse_route_decision(result.content)

    def _parse_route_decision(self, content: str) -> RouteDecision:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            raise LLMError("LLM router did not return JSON", status_code=502)
        try:
            payload = json.loads(match.group(0))
            payload = self._normalize_payload(payload)
            return RouteDecision.model_validate(payload)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise LLMError(f"LLM router returned invalid RouteDecision: {exc}", status_code=502) from exc

    def _normalize_payload(self, payload: dict) -> dict:
        intent_aliases = {
            "greeting": "chat_response",
            "chat": "chat_response",
            "qa": "knowledge_qa",
            "knowledge": "knowledge_qa",
            "analysis": "data_analysis",
            "report": "report_generation",
            "workflow": "workflow_request",
        }
        style_aliases = {
            "friendly": "brief",
            "concise": "brief",
            "short": "brief",
            "professional": "normal",
            "专业诊断": "normal",
            "long": "detailed",
        }
        if payload.get("intent") in intent_aliases:
            payload["intent"] = intent_aliases[payload["intent"]]
        if payload.get("response_style") in style_aliases:
            payload["response_style"] = style_aliases[payload["response_style"]]
        if payload.get("response_style") not in {"brief", "normal", "detailed"}:
            payload["response_style"] = "normal"
        return payload


class StateGateResult(BaseModel):
    allowed: bool
    message: str | None = None


class StateGate:
    def check(self, *, decision: RouteDecision, context: CaseRouteContext) -> StateGateResult:
        if decision.requires_dataset and not context.has_dataset:
            return StateGateResult(
                allowed=False,
                message="当前案例还没有上传设备性能数据文件。请先上传 CSV 文件，上传后我会自动使用该数据进行分析。",
            )
        return StateGateResult(allowed=True)
