from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class LLMConfig(BaseModel):
    provider: Literal["openai_compatible"] = "openai_compatible"
    tool_mode: Literal["native", "prompt_xml_json"] = "native"
    base_url: str = "http://localhost:8001/v1"
    api_key: str | None = None
    model: str = "local-diagnostic-model"
    timeout: float = Field(default=30.0, gt=0)
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)

    @property
    def is_real_llm(self) -> bool:
        return True


def load_dotenv(path: Path | str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def load_llm_config(dotenv_path: Path | str = ".env") -> LLMConfig:
    load_dotenv(dotenv_path)
    return LLMConfig(
        provider=os.getenv("SEMIDIAG_LLM_PROVIDER", "openai_compatible"),  # type: ignore[arg-type]
        tool_mode=os.getenv("SEMIDIAG_LLM_TOOL_MODE", "native"),  # type: ignore[arg-type]
        base_url=os.getenv("SEMIDIAG_LLM_BASE_URL", "http://localhost:8001/v1"),
        api_key=os.getenv("SEMIDIAG_LLM_API_KEY"),
        model=os.getenv("SEMIDIAG_LLM_MODEL", "local-diagnostic-model"),
        timeout=float(os.getenv("SEMIDIAG_LLM_TIMEOUT", "30")),
        temperature=float(os.getenv("SEMIDIAG_LLM_TEMPERATURE", "0.1")),
    )
