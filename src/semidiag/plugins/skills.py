from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class SkillSpec(BaseModel):
    name: str
    description: str
    plugin_id: str
    content: str
    path: str
    triggers: list[str] = Field(default_factory=list)
    max_context_chars: int = 4000

    def context_excerpt(self) -> str:
        return self.content[: self.max_context_chars]

    def summary(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "plugin_id": self.plugin_id,
            "triggers": self.triggers,
            "max_context_chars": self.max_context_chars,
        }


def load_markdown_skill(path: Path) -> SkillSpec:
    text = path.read_text(encoding="utf-8")
    frontmatter, content = _split_frontmatter(text, path)
    return SkillSpec(
        name=_required(frontmatter, "name", path),
        description=_required(frontmatter, "description", path),
        plugin_id=_required(frontmatter, "plugin_id", path),
        content=content.strip(),
        path=str(path),
        triggers=_parse_list(frontmatter.get("triggers", "")),
        max_context_chars=int(frontmatter.get("max_context_chars", 4000)),
    )


def _split_frontmatter(text: str, path: Path) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        raise ValueError(f"skill markdown must start with frontmatter: {path}")
    end = text.find("\n---", 4)
    if end < 0:
        raise ValueError(f"skill markdown frontmatter is not closed: {path}")
    frontmatter_text = text[4:end].strip()
    body = text[end + 4 :].lstrip("\r\n")
    return _parse_frontmatter(frontmatter_text), body


def _parse_frontmatter(text: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise ValueError(f"invalid frontmatter line: {raw_line}")
        key, value = line.split(":", 1)
        parsed[key.strip()] = value.strip().strip('"').strip("'")
    return parsed


def _required(frontmatter: dict[str, str], key: str, path: Path) -> str:
    value = frontmatter.get(key, "").strip()
    if not value:
        raise ValueError(f"skill frontmatter missing {key}: {path}")
    return value


def _parse_list(value: str) -> list[str]:
    normalized = value.strip()
    if not normalized:
        return []
    if normalized.startswith("[") and normalized.endswith("]"):
        normalized = normalized[1:-1]
    return [item.strip().strip('"').strip("'") for item in normalized.split(",") if item.strip()]
