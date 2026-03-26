from __future__ import annotations

import json
from typing import Any, Callable, Protocol
from urllib import request

from pr_agents.models import AgentDecisionAction, AgentEntry, LLMProviderName, SourcePattern


class AgentLLM(Protocol):
    name: str

    def is_configured(self) -> bool:
        ...

    def complete_json(self, *, system_prompt: str, user_prompt: str, model: str, timeout: float) -> str:
        ...


Requester = Callable[[str, dict[str, Any], dict[str, str], float], str]


class FakeLLM:
    name = "fake"

    def is_configured(self) -> bool:
        return True

    def complete_json(self, *, system_prompt: str, user_prompt: str, model: str, timeout: float) -> str:
        del model, timeout
        if "AGENT_DECISION" in system_prompt:
            try:
                payload = json.loads(user_prompt)
                prompt = payload.get("user_message", user_prompt)
            except json.JSONDecodeError:
                prompt = user_prompt
            return json.dumps(self._decision_payload(prompt), ensure_ascii=False)
        if "AGENT_PLAN" in system_prompt:
            payload = json.loads(user_prompt)
            decision = payload.get("decision", payload)
            return json.dumps(self._plan_payload(decision), ensure_ascii=False)
        raise ValueError("unsupported fake llm prompt type")

    def _decision_payload(self, user_prompt: str) -> dict[str, Any]:
        normalized = user_prompt.strip()
        upper = normalized.upper()
        lower = normalized.lower()
        business_code = "B001" if "B001" in upper else "A_DEMO"
        entry = AgentEntry.DATABASE.value if "database" in lower or "数据库" in normalized else AgentEntry.FILE.value

        if self._is_report_summary_request(normalized):
            return {
                "action": AgentDecisionAction.CALL_TOOL.value,
                "tool_name": "summarize_report",
                "tool_input": {"business_code": business_code},
                "response": "",
                "thought_summary": "Use the latest report and summarize its key points.",
            }
        if self._is_report_request(normalized):
            return {
                "action": AgentDecisionAction.CALL_TOOL.value,
                "tool_name": "load_latest_report",
                "tool_input": {"business_code": business_code},
                "response": "",
                "thought_summary": "Load the most recent report from session history.",
            }
        if self._is_chat(normalized, lower):
            return {
                "action": AgentDecisionAction.RESPOND.value,
                "tool_name": None,
                "tool_input": {},
                "response": self._chat_reply(normalized),
                "thought_summary": "Respond directly without tools.",
            }
        if self._looks_like_analysis_request(normalized, lower):
            tool_name = "run_db_analysis_workflow" if entry == AgentEntry.DATABASE.value else "run_file_analysis_workflow"
            return {
                "action": AgentDecisionAction.CALL_TOOL.value,
                "tool_name": tool_name,
                "tool_input": {
                    "business_code": business_code,
                    "entry": entry,
                    "objective": normalized or "Generate analysis results",
                    "chart_type": "scientific_plot",
                    "source_pattern": self._detect_source_pattern(business_code),
                },
                "response": "",
                "thought_summary": "Run the appropriate analysis workflow before replying.",
            }
        return {
            "action": AgentDecisionAction.RESPOND.value,
            "tool_name": None,
            "tool_input": {},
            "response": self._chat_reply(normalized),
            "thought_summary": "Reply directly because no tool is required.",
        }

    def _plan_payload(self, decision: dict[str, Any]) -> dict[str, Any]:
        tool_name = decision["tool_name"]
        business_code = decision["tool_input"].get("business_code", "A_DEMO")
        goal = decision["tool_input"].get("objective", f"Analyze {business_code}")
        first_title = (
            f"Run database analysis workflow for {business_code}"
            if tool_name == "run_db_analysis_workflow"
            else f"Run file analysis workflow for {business_code}"
        )
        return {
            "goal": goal,
            "business_code": business_code,
            "entry": decision["tool_input"].get("entry", AgentEntry.FILE.value),
            "steps": [
                {
                    "step_index": 0,
                    "title": first_title,
                    "tool_name": tool_name,
                    "inputs_summary": {
                        "business_code": business_code,
                        "entry": decision["tool_input"].get("entry", AgentEntry.FILE.value),
                        "chart_type": decision["tool_input"].get("chart_type", "scientific_plot"),
                    },
                },
                {
                    "step_index": 1,
                    "title": "Summarize workflow results for the user",
                    "tool_name": "summarize_session_results",
                    "inputs_summary": {"goal": goal},
                },
            ],
            "expected_outputs": ["chart", "report"],
            "planner_source": self.name,
            "used_fallback": False,
        }

    @staticmethod
    def _detect_source_pattern(business_code: str) -> str:
        if business_code == "B001":
            return SourcePattern.SHARED_FILE.value
        return SourcePattern.PER_BUSINESS_FILE.value

    @staticmethod
    def _is_chat(content: str, lower: str) -> bool:
        greetings = {"hi", "hello", "hey", "你好", "您好", "嗨", "在吗", "你是谁", "你能做什么", "怎么用", "help"}
        return lower in greetings or content in greetings

    @staticmethod
    def _is_report_request(content: str) -> bool:
        lower = content.lower()
        return (
            "show me the report again" in lower
            or "show the report again" in lower
            or "report again" in lower
            or "show latest report" in lower
            or "再看报告" in content
            or "重新看报告" in content
        )

    @staticmethod
    def _is_report_summary_request(content: str) -> bool:
        lower = content.lower()
        return (
            "summarize the report" in lower
            or "summarise the report" in lower
            or "report summary" in lower
            or "key points" in lower
            or "概括这份报告" in content
            or "总结这份报告" in content
            or "报告重点" in content
        )

    @staticmethod
    def _looks_like_analysis_request(content: str, lower: str) -> bool:
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
        return any(marker in lower or marker in content for marker in markers)

    @staticmethod
    def _chat_reply(content: str) -> str:
        normalized = content.strip().lower()
        if normalized in {"hi", "hello", "hey", "你好", "您好", "嗨", "在吗"}:
            return (
                "你好。我可以帮你分析 demo 数据、生成科学绘图和报告。"
                "你可以直接说：请用 A_DEMO 文件数据生成科学绘图和报告。"
            )
        if "你是谁" in content or "你能做什么" in content or "怎么用" in content or normalized == "help":
            return (
                "我是一个任务型分析 Agent。你可以让我跑文件分析、数据库分析、查看报告，"
                "或者概括报告重点。"
            )
        return "我可以直接回复，也可以调用分析工作流。你可以试试文件 demo、数据库 demo，或者让我概括最近的报告。"


class GLMProvider:
    name = LLMProviderName.GLM.value

    def __init__(
        self,
        base_url: str | None,
        api_key: str | None,
        requester: Requester | None = None,
    ) -> None:
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key or ""
        self.requester = requester

    def is_configured(self) -> bool:
        return bool(self.base_url and self.api_key)

    def complete_json(self, *, system_prompt: str, user_prompt: str, model: str, timeout: float) -> str:
        if not self.is_configured():
            raise ValueError("glm provider is not configured")

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}/chat/completions"
        response_text = (
            self.requester(url, payload, headers, timeout)
            if self.requester
            else self._post(url, payload, headers, timeout)
        )
        response_payload = json.loads(response_text)
        return response_payload["choices"][0]["message"]["content"]

    @staticmethod
    def _post(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: float) -> str:
        req = request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8")
