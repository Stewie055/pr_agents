from __future__ import annotations

import json
from typing import Any


def redact_llm_request(request: dict[str, Any]) -> dict[str, Any]:
    redacted = json.loads(json.dumps(request, ensure_ascii=False))
    headers = redacted.get("headers")
    if isinstance(headers, dict) and "Authorization" in headers:
        headers["Authorization"] = "Bearer ***"
    if "api_key" in redacted:
        redacted["api_key"] = "***"
    return redacted
