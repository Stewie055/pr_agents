from __future__ import annotations

import json
from typing import Any, Callable, Protocol
from urllib import error, request

from pydantic import ValidationError

from pr_agents.models import (
    AgentAction,
    AgentEntry,
    AgentIntent,
    IntentMode,
    LLMProviderName,
    SourcePattern,
)


class IntentParser(Protocol):
    mode: IntentMode

    def parse(self, content: str) -> AgentIntent:
        ...


class LLMProvider(Protocol):
    name: LLMProviderName

    def is_configured(self) -> bool:
        ...

    def complete_json(self, *, system_prompt: str, user_prompt: str, model: str, timeout: float) -> str:
        ...


class FakeIntentParser:
    """Stable rules-based parser used during service adaptation and fallback."""

    mode = IntentMode.FAKE

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
                intent_source=self.mode.value,
                used_fallback=False,
            )

        return AgentIntent(
            action=AgentAction.ANALYZE,
            business_code=self._extract_business_code(upper),
            entry=self._detect_entry(lower),
            objective=normalized or "Generate a scientific plot report",
            chart_type=self._detect_chart_type(lower),
            source_pattern=self._detect_source_pattern(upper),
            intent_source=self.mode.value,
            used_fallback=False,
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


Requester = Callable[[str, dict[str, Any], dict[str, str], float], str]


class GLMProvider:
    """Provider adapter for GLM official API."""

    name = LLMProviderName.GLM

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


class LLMIntentParser:
    """Schema-constrained parser backed by a pluggable LLM provider."""

    mode = IntentMode.LLM

    def __init__(
        self,
        provider: LLMProvider,
        model: str | None,
        timeout: float = 30.0,
        fallback_parser: IntentParser | None = None,
    ) -> None:
        self.provider = provider
        self.model = model or ""
        self.timeout = timeout
        self.fallback_parser = fallback_parser

    def parse(self, content: str) -> AgentIntent:
        try:
            if not self.provider.is_configured() or not self.model:
                raise ValueError("llm parser is not configured")
            raw = self.provider.complete_json(
                system_prompt=self._system_prompt(),
                user_prompt=content,
                model=self.model,
                timeout=self.timeout,
            )
            intent = AgentIntent.model_validate(self._extract_json(raw))
            intent.intent_source = self.mode.value
            intent.used_fallback = False
            return intent
        except (ValueError, KeyError, ValidationError, error.URLError, TimeoutError, json.JSONDecodeError):
            if self.fallback_parser is None:
                raise
            fallback = self.fallback_parser.parse(content)
            fallback.intent_source = f"{self.mode.value}_fallback"
            fallback.used_fallback = True
            return fallback

    @staticmethod
    def _system_prompt() -> str:
        return (
            "Return valid JSON only with fields action, business_code, entry, objective, "
            "chart_type, source_pattern. Allowed action: analyze, show_report. "
            "Allowed business_code: A_DEMO, B001. Allowed entry: file, database. "
            "Allowed chart_type: scientific_plot. Allowed source_pattern: per_business_file, shared_file."
        )

    @staticmethod
    def _extract_json(content: str) -> dict[str, Any]:
        stripped = content.strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            stripped = "\n".join(line for line in lines if not line.startswith("```")).strip()
        return json.loads(stripped)
