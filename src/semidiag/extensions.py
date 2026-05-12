from __future__ import annotations

import importlib.util
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any


@dataclass
class ExtensionLoadEvent:
    path: str
    extension_type: str
    status: str
    error: str | None = None


@dataclass
class ExtensionLoadReport:
    events: list[ExtensionLoadEvent] = field(default_factory=list)

    def add(self, *, path: Path, extension_type: str, status: str, error: str | None = None) -> None:
        self.events.append(
            ExtensionLoadEvent(path=str(path), extension_type=extension_type, status=status, error=error)
        )

    def model_dump(self) -> dict[str, Any]:
        return {"extensions": [event.__dict__ for event in self.events]}


class ExtensionLoader:
    def __init__(self, extension_root: Path | str = "business") -> None:
        self.extension_root = Path(extension_root)
        self.report = ExtensionLoadReport()

    def load_tools(self, registry) -> ExtensionLoadReport:
        self._load_directory(self.extension_root / "tools", "tool", registry)
        return self.report

    def load_plugins(self, registry) -> ExtensionLoadReport:
        self._load_directory(self.extension_root / "plugins", "plugin", registry)
        return self.report

    def _load_directory(self, directory: Path, extension_type: str, registry) -> None:
        if not directory.exists():
            return
        for path in sorted(directory.glob("*.py")):
            if path.name.startswith("_"):
                continue
            self._load_file(path=path, extension_type=extension_type, registry=registry)

    def _load_file(self, *, path: Path, extension_type: str, registry) -> None:
        try:
            module = self._import_module(path)
            register = getattr(module, "register", None)
            if not callable(register):
                raise ValueError("extension file must define callable register(registry)")
            register(registry)
        except Exception as exc:
            self.report.add(path=path, extension_type=extension_type, status="error", error=str(exc))
            return
        self.report.add(path=path, extension_type=extension_type, status="loaded")

    def _import_module(self, path: Path) -> ModuleType:
        module_name = f"semidiag_business_{path.stem}_{abs(hash(path))}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot import extension file: {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
