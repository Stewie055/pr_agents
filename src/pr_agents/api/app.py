from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from pr_agents.application import AgentSessionService, TaskApplicationService
from pr_agents.models import (
    AgentRunControlRequest,
    AgentUserMessageRequest,
    DatabaseAnalysisRequest,
    FileAnalysisRequest,
    RegisterDatabaseSourceRequest,
    RegisterFileSourceRequest,
    SessionTasksResponse,
)


def _frontend_dist_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "frontend" / "dist"


def create_api_app(task_service: TaskApplicationService, agent_session_service: AgentSessionService) -> FastAPI:
    app = FastAPI(title="pr_agents API", version="0.1.0")
    frontend_dist_dir = _frontend_dist_dir()
    assets_dir = frontend_dist_dir / "assets"

    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="frontend-assets")

    @app.get("/", response_class=HTMLResponse)
    def webui_home():
        index_path = frontend_dist_dir / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        return HTMLResponse(
            (
                "<html><body><h1>frontend not built</h1>"
                "<p>Build the React app with <code>cd frontend && pnpm install && pnpm build</code>.</p>"
                "<p>Backend APIs remain available under <code>/api/v1</code>.</p>"
                "</body></html>"
            ),
            status_code=503,
        )

    @app.post("/api/v1/tasks/file-analysis")
    def submit_file_analysis(request: FileAnalysisRequest):
        return task_service.submit_file_analysis(request)

    @app.post("/api/v1/tasks/db-analysis")
    def submit_db_analysis(request: DatabaseAnalysisRequest):
        return task_service.submit_db_analysis(request)

    @app.get("/api/v1/tasks/{task_id}")
    def get_task(task_id: str):
        task = task_service.get_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="task not found")
        return task

    @app.post("/api/v1/tasks/{task_id}/cancel")
    def cancel_task(task_id: str):
        response = task_service.cancel_task(task_id)
        if response.message == "task not found":
            raise HTTPException(status_code=404, detail="task not found")
        return response

    @app.get("/api/v1/sessions/{session_id}/tasks")
    def list_session_tasks(session_id: str):
        return SessionTasksResponse(session_id=session_id, tasks=task_service.list_session_tasks(session_id))

    @app.get("/api/v1/artifacts/{artifact_id}")
    def get_artifact(artifact_id: str):
        artifact = task_service.get_artifact(artifact_id)
        if artifact is None:
            raise HTTPException(status_code=404, detail="artifact not found")
        return artifact

    @app.get("/api/v1/artifacts/{artifact_id}/content")
    def read_artifact_content(artifact_id: str):
        try:
            content = task_service.read_artifact_content(artifact_id)
        except ValueError as exc:
            raise HTTPException(status_code=415, detail=str(exc)) from exc
        if content is None:
            raise HTTPException(status_code=404, detail="artifact not found")
        return Response(content=content, media_type="text/plain; charset=utf-8")

    @app.get("/api/v1/artifacts/{artifact_id}/raw")
    def read_artifact_raw(artifact_id: str):
        payload = task_service.read_artifact_raw(artifact_id)
        if payload is None:
            raise HTTPException(status_code=404, detail="artifact not found")
        content, media_type = payload
        return Response(content=content, media_type=media_type)

    @app.post("/api/v1/agent/sessions")
    def create_agent_session():
        return agent_session_service.create_session()

    @app.get("/api/v1/agent/sessions/{session_id}")
    def get_agent_session(session_id: str):
        return agent_session_service.get_session(session_id)

    @app.post("/api/v1/agent/sessions/{session_id}/messages")
    def send_agent_message(session_id: str, request: AgentUserMessageRequest):
        return agent_session_service.start_message_run(session_id, request)

    @app.post("/api/v1/agent/sessions/{session_id}/sources/file")
    def register_agent_file_source(session_id: str, request: RegisterFileSourceRequest):
        return agent_session_service.register_file_source(session_id, request)

    @app.post("/api/v1/agent/sessions/{session_id}/sources/csv-upload")
    async def upload_agent_csv_source(
        session_id: str,
        file: UploadFile = File(...),
        business_code: str = Form("file_analysis"),
    ):
        if not file.filename.lower().endswith(".csv"):
            raise HTTPException(status_code=415, detail="only csv files are supported")
        content = await file.read()
        return agent_session_service.register_uploaded_csv_source(
            session_id,
            file_name=file.filename,
            content=content,
            business_code=business_code,
        )

    @app.post("/api/v1/agent/sessions/{session_id}/sources/database")
    def register_agent_database_source(session_id: str, request: RegisterDatabaseSourceRequest):
        return agent_session_service.register_database_source(session_id, request)

    @app.get("/api/v1/agent/sessions/{session_id}/sources")
    def list_agent_sources(session_id: str):
        return agent_session_service.list_sources(session_id)

    @app.post("/api/v1/agent/sessions/{session_id}/demo-sources/{demo_code}")
    def register_demo_source(session_id: str, demo_code: str):
        try:
            return agent_session_service.register_demo_source(session_id, demo_code)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/v1/agent/sessions/{session_id}/runs/{run_id}/stream")
    def stream_agent_run(session_id: str, run_id: str):
        return StreamingResponse(
            agent_session_service.iter_formatted_sse(session_id, run_id),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    @app.post("/api/v1/agent/sessions/{session_id}/runs/{run_id}/control")
    def control_agent_run(session_id: str, run_id: str, request: AgentRunControlRequest):
        response = agent_session_service.control_run(session_id, run_id, request)
        if not response.applied and response.message == "run not found":
            raise HTTPException(status_code=404, detail="run not found")
        return response

    @app.get("/api/v1/agent/sessions/{session_id}/artifacts/{artifact_id}/content")
    def read_agent_session_artifact_content(session_id: str, artifact_id: str):
        try:
            content = agent_session_service.read_session_artifact_content(session_id, artifact_id)
        except ValueError as exc:
            raise HTTPException(status_code=415, detail=str(exc)) from exc
        if content is None:
            raise HTTPException(status_code=404, detail="artifact not found")
        return Response(content=content, media_type="text/plain; charset=utf-8")

    @app.get("/api/v1/agent/sessions/{session_id}/artifacts/{artifact_id}/raw")
    def read_agent_session_artifact_raw(session_id: str, artifact_id: str):
        payload = agent_session_service.read_session_artifact_raw(session_id, artifact_id)
        if payload is None:
            raise HTTPException(status_code=404, detail="artifact not found")
        content, media_type = payload
        return Response(content=content, media_type=media_type)

    return app
