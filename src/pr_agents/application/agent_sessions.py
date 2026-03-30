from __future__ import annotations

import asyncio
import json
from pathlib import Path
from uuid import uuid4

from pr_agents.agent.runtime import AgentRuntime
from pr_agents.application.tasks import TaskApplicationService
from pr_agents.infrastructure import AgentSessionRepository
from pr_agents.models import (
    AgentMessageStartResponse,
    AgentSourceRecord,
    AgentSourceType,
    AgentRunStatus,
    AgentSessionResponse,
    AgentUserMessageRequest,
    CreateAgentSessionResponse,
    RegisterDatabaseSourceRequest,
    RegisterFileSourceRequest,
    MessageRole,
    MessageType,
)


class AgentSessionService:
    def __init__(
        self,
        session_repository: AgentSessionRepository,
        task_service: TaskApplicationService,
        runtime: AgentRuntime,
        demo_data_path: str,
    ) -> None:
        self.session_repository = session_repository
        self.task_service = task_service
        self.runtime = runtime
        self.demo_data_path = Path(demo_data_path)

    @property
    def intent_mode(self) -> str:
        return self.runtime.mode

    def create_session(self) -> CreateAgentSessionResponse:
        session_id = f"session-{uuid4().hex[:8]}"
        self.session_repository.create_session(session_id)
        self.session_repository.add_message(
            session_id,
            MessageRole.ASSISTANT,
            MessageType.CHAT,
            "Agent session created. Register a file source, register a database source, or start with the file/database demo.",
        )
        return CreateAgentSessionResponse(session_id=session_id)

    def get_session(self, session_id: str) -> AgentSessionResponse:
        self.session_repository.create_session(session_id)
        return AgentSessionResponse(
            session_id=session_id,
            messages=self.session_repository.list_messages(session_id),
            tasks=self.task_service.list_session_tasks(session_id),
            runs=self.session_repository.list_runs(session_id),
            sources=self.session_repository.list_sources(session_id),
        )

    def start_message_run(self, session_id: str, request: AgentUserMessageRequest) -> AgentMessageStartResponse:
        self.session_repository.create_session(session_id)
        message = self.session_repository.add_message(
            session_id,
            MessageRole.USER,
            MessageType.CHAT,
            request.content,
        )
        run = self.session_repository.create_run(
            session_id=session_id,
            goal=request.content,
            intent_mode=self.intent_mode,
            metadata={
                "request_content": request.content,
                "source_id": request.source_id,
                "message_id": message.message_id,
                "state": "queued",
            },
        )
        return AgentMessageStartResponse(
            session_id=session_id,
            run_id=run.run_id,
            message_id=message.message_id,
            stream_url=f"/api/v1/agent/sessions/{session_id}/runs/{run.run_id}/stream",
        )

    async def stream_run_events(self, session_id: str, run_id: str):
        async for event in self.runtime.stream_run_events(session_id, run_id):
            yield event

    async def iter_formatted_sse(self, session_id: str, run_id: str):
        async for event in self.stream_run_events(session_id, run_id):
            yield self._format_event(event)
        yield self._format_event(self.runtime._event("keepalive", session_id, run_id, {"status": "stream_closed"}))

    def handle_message(self, session_id: str, request: AgentUserMessageRequest) -> AgentSessionResponse:
        start = self.start_message_run(session_id, request)
        async def _drain() -> None:
            async for _ in self.stream_run_events(session_id, start.run_id):
                pass
        asyncio.run(_drain())
        return self.get_session(session_id)

    def read_session_artifact_content(self, session_id: str, artifact_id: str) -> str | None:
        task_ids = {task.task_id for task in self.task_service.list_session_tasks(session_id)}
        artifact = self.task_service.get_artifact(artifact_id)
        if artifact is None or artifact.task_id not in task_ids:
            return None
        return self.task_service.read_artifact_content(artifact_id)

    def read_session_artifact_raw(self, session_id: str, artifact_id: str) -> tuple[bytes, str] | None:
        task_ids = {task.task_id for task in self.task_service.list_session_tasks(session_id)}
        artifact = self.task_service.get_artifact(artifact_id)
        if artifact is None or artifact.task_id not in task_ids:
            return None
        return self.task_service.read_artifact_raw(artifact_id)

    def register_file_source(self, session_id: str, request: RegisterFileSourceRequest) -> AgentSourceRecord:
        self.session_repository.create_session(session_id)
        return self.session_repository.register_source(
            session_id=session_id,
            source_type=AgentSourceType.FILE,
            name=request.file_name,
            payload={"file_name": request.file_name, "content": request.content},
            metadata={"source_profile": request.source_profile},
        )

    def register_database_source(self, session_id: str, request: RegisterDatabaseSourceRequest) -> AgentSourceRecord:
        self.session_repository.create_session(session_id)
        return self.session_repository.register_source(
            session_id=session_id,
            source_type=AgentSourceType.DATABASE,
            name=request.query_name,
            payload={"query_name": request.query_name, "sql": request.sql},
            metadata={"source_profile": request.source_profile},
        )

    def list_sources(self, session_id: str) -> list[AgentSourceRecord]:
        self.session_repository.create_session(session_id)
        return self.session_repository.list_sources(session_id)

    def register_demo_source(self, session_id: str, demo_code: str) -> AgentSourceRecord:
        self.session_repository.create_session(session_id)
        if demo_code == "a_demo_file":
            return self.session_repository.register_source(
                session_id=session_id,
                source_type=AgentSourceType.FILE,
                name=self.demo_data_path.name,
                payload={
                    "file_name": self.demo_data_path.name,
                    "content": self.demo_data_path.read_text(encoding="utf-8"),
                },
                metadata={"demo_code": demo_code, "source_profile": {"source_pattern": "per_business_file", "data_version": "demo-v1"}},
            )
        if demo_code == "a_demo_db":
            return self.session_repository.register_source(
                session_id=session_id,
                source_type=AgentSourceType.DATABASE,
                name="demo_query",
                payload={"query_name": "demo_query", "sql": "select * from cleaned_demo_data"},
                metadata={"demo_code": demo_code, "source_profile": {"source_pattern": "per_business_file", "data_version": "demo-v1"}},
            )
        raise ValueError(f"unknown demo code: {demo_code}")

    @staticmethod
    def _format_event(event) -> str:
        return f"event: {event.event}\ndata: {json.dumps(event.model_dump(mode='json'), ensure_ascii=False)}\n\n"
