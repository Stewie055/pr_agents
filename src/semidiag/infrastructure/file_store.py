from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from semidiag.domain import DatasetRecord


class LocalFileStore:
    def __init__(self, root: Path | str = "var/files") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def save_bytes(
        self,
        *,
        case_id: str,
        filename: str,
        content: bytes,
        content_type: str | None = None,
    ) -> DatasetRecord:
        case_dir = self.root / case_id
        case_dir.mkdir(parents=True, exist_ok=True)
        safe_name = Path(filename).name or "dataset.csv"
        stored_name = f"{uuid4().hex[:12]}_{safe_name}"
        path = case_dir / stored_name
        path.write_bytes(content)
        return DatasetRecord(
            case_id=case_id,
            filename=safe_name,
            path=str(path),
            content_type=content_type,
        )
