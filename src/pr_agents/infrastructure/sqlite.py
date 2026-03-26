from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from uuid import uuid4

from pr_agents.models import (
    AgentMessage,
    ArtifactRecord,
    ArtifactType,
    MessageRole,
    MessageType,
    SessionRecord,
    TaskRecord,
    TaskStatus,
)


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class SQLiteRepository:
    def __init__(self, db_path: str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    objective TEXT NOT NULL,
                    input_summary TEXT NOT NULL,
                    result_summary TEXT NOT NULL,
                    error_summary TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT,
                    FOREIGN KEY(session_id) REFERENCES sessions(session_id)
                );

                CREATE TABLE IF NOT EXISTS artifacts (
                    artifact_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    artifact_type TEXT NOT NULL,
                    uri TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(task_id) REFERENCES tasks(task_id)
                );

                CREATE TABLE IF NOT EXISTS agent_messages (
                    message_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    message_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(session_id)
                );
                """
            )


class TaskRepository(SQLiteRepository):
    def upsert_session(self, session_id: str) -> SessionRecord:
        now = utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions(session_id, created_at, updated_at)
                VALUES(?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET updated_at=excluded.updated_at
                """,
                (session_id, now, now),
            )
            row = conn.execute(
                "SELECT session_id, created_at, updated_at FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        return SessionRecord(**dict(row))

    def create_task(
        self,
        task_id: str,
        session_id: str,
        task_type: str,
        objective: str,
        input_summary: dict,
    ) -> TaskRecord:
        self.upsert_session(session_id)
        now = utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO tasks(
                    task_id, session_id, task_type, status, objective, input_summary,
                    result_summary, error_summary, created_at, updated_at, completed_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    session_id,
                    task_type,
                    TaskStatus.PENDING.value,
                    objective,
                    json.dumps(input_summary),
                    json.dumps({}),
                    json.dumps({}),
                    now,
                    now,
                    None,
                ),
            )
            row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        return self._task_from_row(row)

    def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        result_summary: dict | None = None,
        error_summary: dict | None = None,
    ) -> TaskRecord:
        now = utc_now()
        completed_at = now if status in {TaskStatus.SUCCEEDED, TaskStatus.FAILED} else None
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE tasks
                SET status = ?, result_summary = ?, error_summary = ?, updated_at = ?, completed_at = COALESCE(?, completed_at)
                WHERE task_id = ?
                """,
                (
                    status.value,
                    json.dumps(result_summary or {}),
                    json.dumps(error_summary or {}),
                    now,
                    completed_at,
                    task_id,
                ),
            )
            row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        return self._task_from_row(row)

    def get_task(self, task_id: str) -> TaskRecord | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        return self._task_from_row(row) if row else None

    def list_session_tasks(self, session_id: str) -> list[TaskRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE session_id = ? ORDER BY created_at ASC",
                (session_id,),
            ).fetchall()
        return [self._task_from_row(row) for row in rows]

    @staticmethod
    def _task_from_row(row: sqlite3.Row) -> TaskRecord:
        return TaskRecord(
            task_id=row["task_id"],
            session_id=row["session_id"],
            task_type=row["task_type"],
            status=TaskStatus(row["status"]),
            objective=row["objective"],
            input_summary=json.loads(row["input_summary"]),
            result_summary=json.loads(row["result_summary"]),
            error_summary=json.loads(row["error_summary"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            completed_at=row["completed_at"],
        )


class ArtifactRepository(SQLiteRepository):
    def register_artifact(self, task_id: str, artifact_type: ArtifactType, uri: str, filename: str, metadata: dict) -> ArtifactRecord:
        now = utc_now()
        artifact_id = metadata.get("artifact_id") or Path(uri).stem
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO artifacts(
                    artifact_id, task_id, artifact_type, uri, filename, metadata, created_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (artifact_id, task_id, artifact_type.value, uri, filename, json.dumps(metadata), now),
            )
            row = conn.execute("SELECT * FROM artifacts WHERE artifact_id = ?", (artifact_id,)).fetchone()
        return self._artifact_from_row(row)

    def get_artifact(self, artifact_id: str) -> ArtifactRecord | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM artifacts WHERE artifact_id = ?", (artifact_id,)).fetchone()
        return self._artifact_from_row(row) if row else None

    def list_task_artifacts(self, task_id: str) -> list[ArtifactRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM artifacts WHERE task_id = ? ORDER BY created_at ASC",
                (task_id,),
            ).fetchall()
        return [self._artifact_from_row(row) for row in rows]

    @staticmethod
    def _artifact_from_row(row: sqlite3.Row) -> ArtifactRecord:
        return ArtifactRecord(
            artifact_id=row["artifact_id"],
            task_id=row["task_id"],
            artifact_type=ArtifactType(row["artifact_type"]),
            uri=row["uri"],
            filename=row["filename"],
            metadata=json.loads(row["metadata"]),
            created_at=row["created_at"],
        )


class AgentSessionRepository(SQLiteRepository):
    def create_session(self, session_id: str) -> SessionRecord:
        now = utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO sessions(session_id, created_at, updated_at)
                VALUES(?, ?, ?)
                """,
                (session_id, now, now),
            )
            conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
                (now, session_id),
            )
            row = conn.execute(
                "SELECT session_id, created_at, updated_at FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        return SessionRecord(**dict(row))

    def add_message(
        self,
        session_id: str,
        role: MessageRole,
        message_type: MessageType,
        content: str,
        metadata: dict | None = None,
    ) -> AgentMessage:
        self.create_session(session_id)
        now = utc_now()
        message_id = f"msg-{uuid4().hex[:8]}"
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO agent_messages(message_id, session_id, role, message_type, content, metadata, created_at)
                VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    session_id,
                    role.value,
                    message_type.value,
                    content,
                    json.dumps(metadata or {}),
                    now,
                ),
            )
            conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
                (now, session_id),
            )
            row = conn.execute(
                "SELECT * FROM agent_messages WHERE message_id = ?",
                (message_id,),
            ).fetchone()
        return self._message_from_row(row)

    def list_messages(self, session_id: str) -> list[AgentMessage]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM agent_messages WHERE session_id = ? ORDER BY created_at ASC",
                (session_id,),
            ).fetchall()
        return [self._message_from_row(row) for row in rows]

    @staticmethod
    def _message_from_row(row: sqlite3.Row) -> AgentMessage:
        return AgentMessage(
            message_id=row["message_id"],
            session_id=row["session_id"],
            role=MessageRole(row["role"]),
            message_type=MessageType(row["message_type"]),
            content=row["content"],
            metadata=json.loads(row["metadata"]),
            created_at=row["created_at"],
        )
