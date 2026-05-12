from __future__ import annotations

import json
import re
from typing import Any

from semidiag.agent.llm_contracts import LLMError, LLMToolCall


class PromptXmlJsonParser:
    @staticmethod
    def parse(content: str) -> dict[str, Any]:
        tool_blocks = re.findall(r"<tool_calls>\s*(.*?)\s*</tool_calls>", content, flags=re.DOTALL | re.IGNORECASE)
        final_blocks = re.findall(r"<final_answer>\s*(.*?)\s*</final_answer>", content, flags=re.DOTALL | re.IGNORECASE)
        if tool_blocks and final_blocks:
            raise LLMError("Prompt XML+JSON output must not contain both tool_calls and final_answer", status_code=502)
        if not tool_blocks and not final_blocks:
            raise LLMError("Prompt XML+JSON output must contain tool_calls or final_answer", status_code=502)
        if final_blocks:
            return {"action": "final_answer", "content": final_blocks[-1].strip()}
        if len(tool_blocks) > 1:
            raise LLMError("Prompt XML+JSON output must contain only one tool_calls block", status_code=502)
        try:
            payload = json.loads(tool_blocks[0])
        except json.JSONDecodeError as exc:
            raise LLMError("Prompt XML+JSON tool_calls block must contain valid JSON", status_code=502) from exc
        if not isinstance(payload, list) or not payload:
            raise LLMError("Prompt XML+JSON tool_calls must be a non-empty JSON array", status_code=502)
        calls: list[LLMToolCall] = []
        for index, item in enumerate(payload, start=1):
            if not isinstance(item, dict):
                raise LLMError("Prompt XML+JSON tool call must be an object", status_code=502)
            name = item.get("name")
            arguments = item.get("arguments", {})
            if not isinstance(name, str) or not name:
                raise LLMError("Prompt XML+JSON tool call name must be a string", status_code=502)
            if not isinstance(arguments, dict):
                raise LLMError(f"Prompt XML+JSON arguments must be an object for {name}", status_code=502)
            calls.append(LLMToolCall(id=str(item.get("id") or f"call_{index}"), name=name, arguments=arguments))
        return {"action": "tool_calls", "tool_calls": calls}
