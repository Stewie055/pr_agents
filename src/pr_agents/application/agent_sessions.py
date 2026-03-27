from __future__ import annotations

import asyncio
import json
from uuid import uuid4

from pr_agents.agent.runtime import AgentRuntime
from pr_agents.application.tasks import TaskApplicationService
from pr_agents.infrastructure import AgentSessionRepository
from pr_agents.models import (
    AgentControlState,
    AgentMessageStartResponse,
    AgentRunControlAction,
    AgentRunControlRequest,
    AgentRunControlResponse,
    AgentRunStatus,
    AgentSessionResponse,
    AgentUserMessageRequest,
    CreateAgentSessionResponse,
    MessageRole,
    MessageType,
)


class AgentSessionService:
    def __init__(
        self,
        session_repository: AgentSessionRepository,
        task_service: TaskApplicationService,
        runtime: AgentRuntime,
    ) -> None:
        self.session_repository = session_repository
        self.task_service = task_service
        self.runtime = runtime

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
            "Agent session created. Start with the file demo, the database demo, or ask for the latest report.",
        )
        return CreateAgentSessionResponse(session_id=session_id)

    def get_session(self, session_id: str) -> AgentSessionResponse:
        self.session_repository.create_session(session_id)
        return AgentSessionResponse(
            session_id=session_id,
            messages=self.session_repository.list_messages(session_id),
            tasks=self.task_service.list_session_tasks(session_id),
            runs=self.session_repository.list_runs(session_id),
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

    def create_rerun(
        self,
        session_id: str,
        source_run_id: str,
        step_id: str | None = None,
        note: str = "",
    ) -> AgentMessageStartResponse | None:
        source_run = self.session_repository.get_run(source_run_id)
        if source_run is None or source_run.session_id != session_id:
            return None
        run = self.session_repository.create_run(
            session_id=session_id,
            goal=source_run.goal,
            intent_mode=self.intent_mode,
            metadata={
                "request_content": source_run.goal,
                "state": "queued",
                "rerun_source_run_id": source_run_id,
                "rerun_step_id": step_id,
                "rerun_note": note,
            },
        )
        return AgentMessageStartResponse(
            session_id=session_id,
            run_id=run.run_id,
            message_id="",
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

    def control_run(
        self,
        session_id: str,
        run_id: str,
        request: AgentRunControlRequest,
    ) -> AgentRunControlResponse:
        run = self.session_repository.get_run(run_id)
        if run is None or run.session_id != session_id:
            return AgentRunControlResponse(
                session_id=session_id,
                run_id=run_id,
                action=request.action,
                applied=False,
                control_state=AgentControlState.RUNNING,
                message="run not found",
                run=None,
            )

        if request.action == AgentRunControlAction.PAUSE:
            updated = self.session_repository.set_run_control_state(run_id, AgentControlState.PAUSED, request.note)
            message = "Run paused." if updated else "run not found"
            return AgentRunControlResponse(
                session_id=session_id,
                run_id=run_id,
                action=request.action,
                applied=updated is not None,
                control_state=AgentControlState.PAUSED,
                message=message,
                run=updated,
            )

        if request.action == AgentRunControlAction.RESUME:
            updated = self.session_repository.set_run_control_state(run_id, AgentControlState.RUNNING, request.note)
            message = "Run resumed." if updated else "run not found"
            return AgentRunControlResponse(
                session_id=session_id,
                run_id=run_id,
                action=request.action,
                applied=updated is not None,
                control_state=AgentControlState.RUNNING,
                message=message,
                run=updated,
            )

        metadata = {
            "last_control_action": request.action.value,
            "last_control_note": request.note,
        }
        if request.step_id:
            metadata["last_control_step_id"] = request.step_id
        if request.state_patch:
            metadata["last_state_patch"] = request.state_patch
        updated = self.session_repository.merge_run_metadata(run_id, metadata)
        control_state = AgentControlState((updated.metadata or {}).get("control_state", AgentControlState.RUNNING.value)) if updated else AgentControlState.RUNNING
        if request.action == AgentRunControlAction.RERUN_STEP:
            rerun = self.create_rerun(session_id, run_id, request.step_id, request.note)
            return AgentRunControlResponse(
                session_id=session_id,
                run_id=run_id,
                action=request.action,
                applied=updated is not None and rerun is not None,
                control_state=control_state,
                message="Rerun started.",
                run=updated,
                spawned_run_id=rerun.run_id if rerun else None,
                stream_url=rerun.stream_url if rerun else None,
            )
        return AgentRunControlResponse(
            session_id=session_id,
            run_id=run_id,
            action=request.action,
            applied=updated is not None,
            control_state=control_state,
            message="State modification request recorded.",
            run=updated,
        )

    @staticmethod
    def _format_event(event) -> str:
        return f"event: {event.event}\ndata: {json.dumps(event.model_dump(mode='json'), ensure_ascii=False)}\n\n"
