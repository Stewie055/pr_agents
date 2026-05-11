from __future__ import annotations

import os
from pathlib import Path
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
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
