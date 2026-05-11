from __future__ import annotations

import json
import os
from pathlib import Path
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from semidiag.agent import AgentRuntime
from semidiag.agent.llm import LLMError, build_llm_provider
from semidiag.config import load_llm_config
from semidiag.infrastructure.file_store import LocalFileStore
from semidiag.infrastructure.repository import SQLiteRepository
from semidiag.tools import build_default_registry


class CreateCaseRequest(BaseModel):
    title: str
    equipment_type: str = "generic_semiconductor_tool"


class MessageRequest(BaseModel):
    content: str
    dataset_id: str | None = None


class AppState:
    def __init__(self, root: Path | str = "var") -> None:
        root_path = Path(root)
        self.repository = SQLiteRepository(root_path / "semidiag.sqlite3")
        self.file_store = LocalFileStore(root_path / "files")
        llm_provider = build_llm_provider(load_llm_config())
        self.agent = AgentRuntime(self.repository, registry=build_default_registry(), llm=llm_provider)


SENSITIVE_KEYS = {"authorization", "api_key", "apikey", "token", "secret", "password"}
MAX_TRACE_STRING_LENGTH = 4000


def redact_trace_value(value):
    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            if any(secret in str(key).lower() for secret in SENSITIVE_KEYS):
                redacted[key] = "***"
            else:
                redacted[key] = redact_trace_value(item)
        return redacted
    if isinstance(value, list):
        return [redact_trace_value(item) for item in value]
    if isinstance(value, str) and len(value) > MAX_TRACE_STRING_LENGTH:
        return {
            "truncated": True,
            "length": len(value),
            "preview": value[:MAX_TRACE_STRING_LENGTH],
        }
    return value


def build_case_trace(case_id: str, repository: SQLiteRepository) -> dict:
    case = repository.get_case(case_id)
    if case is None:
        raise KeyError(case_id)
    llm_events = []
    for event in repository.list_case_llm_audit_events(case_id):
        payload = event.model_dump(mode="json")
        payload["request"] = redact_trace_value(payload.get("request") or {})
        payload["response"] = redact_trace_value(payload.get("response")) if payload.get("response") is not None else None
        llm_events.append(payload)
    return {
        "case": case.model_dump(mode="json"),
        "messages": [item.model_dump(mode="json") for item in repository.list_case_messages(case_id)],
        "agent_steps": [item.model_dump(mode="json") for item in repository.list_case_agent_step_traces(case_id)],
        "tool_traces": [item.model_dump(mode="json") for item in repository.list_case_tool_traces(case_id)],
        "llm_audit_events": llm_events,
        "artifacts": [
            {
                "id": item.id,
                "kind": item.kind,
                "title": item.title,
                "summary": item.summary,
                "created_at": item.created_at.isoformat(),
            }
            for item in repository.list_case_artifacts(case_id)
        ],
        "evidence": [
            {
                "id": item.id,
                "type": item.evidence_type,
                "title": item.title,
                "summary": item.summary,
                "created_at": item.created_at.isoformat(),
            }
            for item in repository.list_case_evidence(case_id)
        ],
    }


def create_app(state: AppState | None = None) -> FastAPI:
    app_state = state or AppState(os.getenv("SEMIDIAG_VAR_DIR", "var"))
    app = FastAPI(title="Semiconductor Diagnostic Agent", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def get_state() -> AppState:
        return app_state

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/tools")
    def list_tools(current=Depends(get_state)):
        return {"tools": [tool.model_dump() for tool in current.agent.registry.list_tools()]}

    @app.post("/api/cases")
    def create_case(request: CreateCaseRequest, current=Depends(get_state)):
        case = current.repository.create_case(request.title, request.equipment_type)
        return case

    @app.get("/api/cases")
    def list_cases(current=Depends(get_state)):
        return {"cases": current.repository.list_cases()}

    @app.get("/api/cases/{case_id}")
    def get_case(case_id: str, current=Depends(get_state)):
        try:
            return current.repository.case_snapshot(case_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="case not found") from exc

    @app.get("/api/cases/{case_id}/trace")
    def get_case_trace(case_id: str, current=Depends(get_state)):
        try:
            return build_case_trace(case_id, current.repository)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="case not found") from exc

    @app.get("/api/cases/{case_id}/trace/export")
    def export_case_trace(case_id: str, current=Depends(get_state)):
        try:
            payload = build_case_trace(case_id, current.repository)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="case not found") from exc
        return Response(
            content=json.dumps(payload, ensure_ascii=False, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{case_id}-trace.json"'},
        )

    @app.post("/api/cases/{case_id}/files")
    async def upload_file(
        case_id: str,
        file: UploadFile = File(),
        current=Depends(get_state),
    ):
        if current.repository.get_case(case_id) is None:
            raise HTTPException(status_code=404, detail="case not found")
        content = await file.read()
        dataset = current.file_store.save_bytes(
            case_id=case_id,
            filename=file.filename or "dataset.csv",
            content=content,
            content_type=file.content_type,
        )
        current.repository.add_dataset(dataset)
        return dataset

    @app.post("/api/cases/{case_id}/messages")
    def post_message(case_id: str, request: MessageRequest, current=Depends(get_state)):
        try:
            result = current.agent.handle_user_message(
                case_id=case_id,
                content=request.content,
                dataset_id=request.dataset_id,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="case not found") from exc
        except LLMError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
        return {
            "message": result.message,
            "summary": result.summary,
            "artifacts": result.artifacts,
            "tool_traces": result.tool_traces,
        }

    return app


app = create_app()


def run() -> None:
    import uvicorn

    uvicorn.run("semidiag.api.main:app", host="0.0.0.0", port=8000, reload=True)
