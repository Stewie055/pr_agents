from __future__ import annotations

from fastapi import FastAPI, HTTPException, Response

from pr_agents.application import TaskApplicationService
from pr_agents.models import DatabaseAnalysisRequest, FileAnalysisRequest, SessionTasksResponse


def create_api_app(task_service: TaskApplicationService) -> FastAPI:
    app = FastAPI(title="pr_agents API", version="0.1.0")

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

    return app
