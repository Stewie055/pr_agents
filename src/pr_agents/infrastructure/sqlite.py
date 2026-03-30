from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from uuid import uuid4

from pr_agents.models import (
    AgentMessage,
    AgentPlanStep,
    AgentRun,
    AgentRunStatus,
    AgentSourceRecord,
    AgentSourceType,
    AgentStepStatus,
    ArtifactRecord,
    ArtifactType,
    MessageRole,
    MessageType,
    SessionRecord,
    TaskRecord,
    TaskStatus,
    WorkflowResult,
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

                CREATE TABLE IF NOT EXISTS agent_sources (
                    source_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(session_id)
                );

                CREATE TABLE IF NOT EXISTS task_results (
                    task_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(task_id) REFERENCES tasks(task_id)
                );

                CREATE TABLE IF NOT EXISTS agent_runs (
                    run_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    goal TEXT NOT NULL,
                    status TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    intent_mode TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(session_id)
                );

                CREATE TABLE IF NOT EXISTS agent_run_steps (
                    step_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    step_index INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    inputs_summary TEXT NOT NULL,
                    observation_summary TEXT NOT NULL,
                    error_summary TEXT NOT NULL,
                    task_id TEXT,
                    artifact_ids TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES agent_runs(run_id)
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

    def save_workflow_result(self, task_id: str, result: WorkflowResult) -> None:
        now = utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO task_results(task_id, payload, updated_at)
                VALUES(?, ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at
                """,
                (task_id, result.model_dump_json(), now),
            )

    def load_workflow_result(self, task_id: str) -> WorkflowResult | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM task_results WHERE task_id = ?",
                (task_id,),
            ).fetchone()
        if row is None:
            return None
        return WorkflowResult.model_validate_json(row["payload"])

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

    def register_source(
        self,
        session_id: str,
        source_type: AgentSourceType,
        name: str,
        payload: dict,
        metadata: dict | None = None,
    ) -> AgentSourceRecord:
        self.create_session(session_id)
        now = utc_now()
        source_id = f"src-{uuid4().hex[:8]}"
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO agent_sources(source_id, session_id, source_type, name, payload, metadata, created_at)
                VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_id,
                    session_id,
                    source_type.value,
                    name,
                    json.dumps(payload),
                    json.dumps(metadata or {}),
                    now,
                ),
            )
            conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
                (now, session_id),
            )
            row = conn.execute("SELECT * FROM agent_sources WHERE source_id = ?", (source_id,)).fetchone()
        return self._source_from_row(row)

    def get_source(self, source_id: str) -> AgentSourceRecord | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM agent_sources WHERE source_id = ?", (source_id,)).fetchone()
        return self._source_from_row(row) if row else None

    def get_session_source(self, session_id: str, source_id: str) -> AgentSourceRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM agent_sources WHERE session_id = ? AND source_id = ?",
                (session_id, source_id),
            ).fetchone()
        return self._source_from_row(row) if row else None

    def list_sources(self, session_id: str) -> list[AgentSourceRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM agent_sources WHERE session_id = ? ORDER BY created_at ASC",
                (session_id,),
            ).fetchall()
        return [self._source_from_row(row) for row in rows]

    def create_run(
        self,
        session_id: str,
        goal: str,
        intent_mode: str,
        metadata: dict | None = None,
    ) -> AgentRun:
        self.create_session(session_id)
        now = utc_now()
        run_id = f"run-{uuid4().hex[:8]}"
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO agent_runs(run_id, session_id, goal, status, summary, intent_mode, metadata, created_at, updated_at)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    session_id,
                    goal,
                    AgentRunStatus.PLANNED.value,
                    "",
                    intent_mode,
                    json.dumps(metadata or {}),
                    now,
                    now,
                ),
            )
            row = conn.execute("SELECT * FROM agent_runs WHERE run_id = ?", (run_id,)).fetchone()
        return self._run_from_row(row, [])

    def get_run(self, run_id: str) -> AgentRun | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM agent_runs WHERE run_id = ?", (run_id,)).fetchone()
            if row is None:
                return None
            steps = conn.execute(
                "SELECT * FROM agent_run_steps WHERE run_id = ? ORDER BY step_index ASC",
                (run_id,),
            ).fetchall()
        return self._run_from_row(row, [self._step_from_row(step) for step in steps])

    def update_run(
        self,
        run_id: str,
        status: AgentRunStatus,
        summary: str = "",
        metadata: dict | None = None,
    ) -> AgentRun | None:
        now = utc_now()
        with self._connect() as conn:
            current = conn.execute("SELECT metadata FROM agent_runs WHERE run_id = ?", (run_id,)).fetchone()
            if current is None:
                return None
            merged_metadata = json.loads(current["metadata"])
            if metadata:
                merged_metadata.update(metadata)
            conn.execute(
                """
                UPDATE agent_runs
                SET status = ?, summary = ?, metadata = ?, updated_at = ?
                WHERE run_id = ?
                """,
                (status.value, summary, json.dumps(merged_metadata), now, run_id),
            )
            row = conn.execute("SELECT * FROM agent_runs WHERE run_id = ?", (run_id,)).fetchone()
            steps = conn.execute(
                "SELECT * FROM agent_run_steps WHERE run_id = ? ORDER BY step_index ASC",
                (run_id,),
            ).fetchall()
        return self._run_from_row(row, [self._step_from_row(step) for step in steps])

    def create_run_step(
        self,
        run_id: str,
        step_index: int,
        title: str,
        tool_name: str,
        inputs_summary: dict | None = None,
    ) -> AgentPlanStep:
        now = utc_now()
        step_id = f"step-{uuid4().hex[:8]}"
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO agent_run_steps(
                    step_id, run_id, step_index, title, tool_name, status, inputs_summary,
                    observation_summary, error_summary, task_id, artifact_ids, created_at, updated_at
                )
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    step_id,
                    run_id,
                    step_index,
                    title,
                    tool_name,
                    AgentStepStatus.PENDING.value,
                    json.dumps(inputs_summary or {}),
                    json.dumps({}),
                    json.dumps({}),
                    None,
                    json.dumps([]),
                    now,
                    now,
                ),
            )
            row = conn.execute("SELECT * FROM agent_run_steps WHERE step_id = ?", (step_id,)).fetchone()
        return self._step_from_row(row)

    def update_run_step(
        self,
        step_id: str,
        status: AgentStepStatus,
        observation_summary: dict | None = None,
        error_summary: dict | None = None,
        task_id: str | None = None,
        artifact_ids: list[str] | None = None,
    ) -> AgentPlanStep | None:
        now = utc_now()
        with self._connect() as conn:
            current = conn.execute("SELECT * FROM agent_run_steps WHERE step_id = ?", (step_id,)).fetchone()
            if current is None:
                return None
            current_observation = json.loads(current["observation_summary"])
            current_error = json.loads(current["error_summary"])
            current_artifact_ids = json.loads(current["artifact_ids"])
            if observation_summary:
                current_observation.update(observation_summary)
            if error_summary:
                current_error.update(error_summary)
            if artifact_ids:
                current_artifact_ids = artifact_ids
            conn.execute(
                """
                UPDATE agent_run_steps
                SET status = ?, observation_summary = ?, error_summary = ?, task_id = COALESCE(?, task_id),
                    artifact_ids = ?, updated_at = ?
                WHERE step_id = ?
                """,
                (
                    status.value,
                    json.dumps(current_observation),
                    json.dumps(current_error),
                    task_id,
                    json.dumps(current_artifact_ids),
                    now,
                    step_id,
                ),
            )
            row = conn.execute("SELECT * FROM agent_run_steps WHERE step_id = ?", (step_id,)).fetchone()
        return self._step_from_row(row)

    def list_runs(self, session_id: str) -> list[AgentRun]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM agent_runs WHERE session_id = ? ORDER BY created_at ASC",
                (session_id,),
            ).fetchall()
            step_rows = conn.execute(
                """
                SELECT s.* FROM agent_run_steps s
                JOIN agent_runs r ON r.run_id = s.run_id
                WHERE r.session_id = ?
                ORDER BY s.step_index ASC, s.created_at ASC
                """,
                (session_id,),
            ).fetchall()
        steps_by_run: dict[str, list[AgentPlanStep]] = {}
        for row in step_rows:
            step = self._step_from_row(row)
            steps_by_run.setdefault(step.run_id, []).append(step)
        return [self._run_from_row(row, steps_by_run.get(row["run_id"], [])) for row in rows]

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

    @staticmethod
    def _source_from_row(row: sqlite3.Row) -> AgentSourceRecord:
        return AgentSourceRecord(
            source_id=row["source_id"],
            session_id=row["session_id"],
            source_type=AgentSourceType(row["source_type"]),
            name=row["name"],
            payload=json.loads(row["payload"]),
            metadata=json.loads(row["metadata"]),
            created_at=row["created_at"],
        )

    @staticmethod
    def _step_from_row(row: sqlite3.Row) -> AgentPlanStep:
        return AgentPlanStep(
            step_id=row["step_id"],
            run_id=row["run_id"],
            step_index=row["step_index"],
            title=row["title"],
            tool_name=row["tool_name"],
            status=AgentStepStatus(row["status"]),
            inputs_summary=json.loads(row["inputs_summary"]),
            observation_summary=json.loads(row["observation_summary"]),
            error_summary=json.loads(row["error_summary"]),
            task_id=row["task_id"],
            artifact_ids=json.loads(row["artifact_ids"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _run_from_row(row: sqlite3.Row, steps: list[AgentPlanStep]) -> AgentRun:
        return AgentRun(
            run_id=row["run_id"],
            session_id=row["session_id"],
            goal=row["goal"],
            status=AgentRunStatus(row["status"]),
            summary=row["summary"],
            intent_mode=row["intent_mode"],
            metadata=json.loads(row["metadata"]),
            steps=steps,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
