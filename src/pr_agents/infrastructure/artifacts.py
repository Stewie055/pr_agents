from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from pr_agents.models import ArtifactRef, ArtifactType, TaskContext


class ArtifactStore:
    """Persists workflow artifacts under a task-scoped workspace."""

    def __init__(self, base_dir: str = "artifacts") -> None:
        self.base_dir = Path(base_dir)

    def task_dir(self, context: TaskContext) -> Path:
        path = self.base_dir / context.session_id / context.task_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save_text(
        self,
        context: TaskContext,
        artifact_type: ArtifactType,
        filename: str,
        content: str,
    ) -> ArtifactRef:
        task_dir = self.task_dir(context)
        path = task_dir / filename
        path.write_text(content, encoding="utf-8")
        return ArtifactRef(
            artifact_id=f"{artifact_type.value}-{uuid4().hex[:8]}",
            artifact_type=artifact_type,
            uri=str(path),
            metadata={"filename": filename},
        )
