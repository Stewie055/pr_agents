from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel

from business.file_classifiers.lt_log_metadata import detect_file_metadata
from semidiag.agent import AgentRuntime
from semidiag.agent.llm import LLMError, build_llm_provider
from semidiag.config import load_llm_config
from semidiag.domain import KnowledgeRecord, WorkflowTemplate
from semidiag.extensions import ExtensionLoader
from semidiag.infrastructure.file_store import LocalFileStore
from semidiag.infrastructure.metrics import SQLiteMetricRepository
from semidiag.infrastructure.repository import SQLiteRepository
from semidiag.infrastructure.tasks import InProcessTaskQueue
from semidiag.plugins import CalibrationPluginRegistry, CalibrationSelection, GenericEquipmentPlugin, LTEquipmentPlugin, PluginRegistry
from semidiag.tools import ToolContext, build_default_registry


class CreateCaseRequest(BaseModel):
    title: str
    equipment_type: str = "generic_semiconductor_tool"


class MessageRequest(BaseModel):
    content: str
    dataset_id: str | None = None


class CreateKnowledgeRequest(BaseModel):
    title: str
    content: str
    source: str = "local"


class CreateWorkflowRequest(BaseModel):
    name: str
    description: str = ""


class AppState:
    def __init__(self, root: Path | str = "var") -> None:
        root_path = Path(root)
        self.repository = SQLiteRepository(root_path / "semidiag.sqlite3")
        self.metric_repository = SQLiteMetricRepository(root_path / "metrics.sqlite3")
        self.task_queue = InProcessTaskQueue()
        self.file_store = LocalFileStore(root_path / "files")
        self.generated_root = root_path / "generated"
        llm_provider = build_llm_provider(load_llm_config())
        self.plugin = GenericEquipmentPlugin()
        self.lt_plugin = LTEquipmentPlugin()
        self.plugin_registry = PluginRegistry([self.plugin, self.lt_plugin])
        self.calibration_registry = CalibrationPluginRegistry()
        self.extension_loader = ExtensionLoader(os.getenv("SEMIDIAG_EXTENSION_DIR", "business"))
        self.tool_registry = build_default_registry()
        self.extension_loader.load_tools(self.tool_registry)
        self.extension_loader.load_plugins(self.calibration_registry)
        self.extension_loader.load_plugin_skills(self.calibration_registry)
        self.agent = AgentRuntime(
            self.repository,
            registry=self.tool_registry,
            llm=llm_provider,
            generated_root=str(self.generated_root),
            plugin_registry=self.plugin_registry,
            calibration_registry=self.calibration_registry,
            metric_repository=self.metric_repository,
            task_queue=self.task_queue,
        )


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
    return redact_trace_value({
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
    })


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

    def sse_event(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/tools")
    def list_tools(case_id: str | None = None, content: str | None = None, current=Depends(get_state)):
        registry = current.agent.registry
        if case_id and content:
            selection = current.agent._select_calibration_plugins(case_id=case_id, content=content)
            registry = current.agent._build_active_tool_registry(case_id=case_id, actor="engineer", selection=selection)
        return {"tools": [tool.model_dump() for tool in registry.list_tools()]}

    @app.get("/api/plugins")
    def list_plugins(current=Depends(get_state)):
        return {
            "plugins": [
                {"equipment_type": plugin.equipment_type, "display_name": plugin.display_name}
                for plugin in current.plugin_registry.list_plugins()
            ]
        }

    @app.get("/api/calibrations")
    def list_calibrations(current=Depends(get_state)):
        return {
            "calibrations": [
                {
                    **plugin.manifest.model_dump(mode="json"),
                    "status": plugin.status,
                    "config_errors": plugin.config_errors,
                    "implementation_path": plugin.implementation_path,
                    "tools": [tool.definition.model_dump(mode="json") for tool in plugin.tools],
                    "skills": [skill.summary() for skill in plugin.skills],
                }
                for plugin in current.calibration_registry.list_plugins()
            ]
        }

    @app.get("/api/extensions")
    def list_extensions(current=Depends(get_state)):
        return current.extension_loader.report.model_dump()

    @app.get("/api/tasks")
    def list_tasks(current=Depends(get_state)):
        return {"tasks": [task.model_dump(mode="json") for task in current.task_queue.list_tasks()]}

    @app.get("/api/tasks/{task_id}")
    def get_task(task_id: str, current=Depends(get_state)):
        task = current.task_queue.get(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="task not found")
        return task

    @app.post("/api/tasks/{task_id}/cancel")
    def cancel_task(task_id: str, current=Depends(get_state)):
        task = current.task_queue.cancel(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="task not found")
        return task

    @app.post("/api/knowledge")
    def create_knowledge(request: CreateKnowledgeRequest, current=Depends(get_state)):
        return current.repository.add_knowledge(
            KnowledgeRecord(title=request.title, content=request.content, source=request.source)
        )

    @app.get("/api/knowledge")
    def list_knowledge(q: str | None = None, current=Depends(get_state)):
        items = current.repository.search_knowledge(q) if q else current.repository.list_knowledge()
        return {"knowledge": [item.model_dump(mode="json") for item in items]}

    @app.post("/api/cases/{case_id}/workflows")
    def create_workflow_from_case(case_id: str, request: CreateWorkflowRequest, current=Depends(get_state)):
        if current.repository.get_case(case_id) is None:
            raise HTTPException(status_code=404, detail="case not found")
        traces = [
            trace
            for trace in current.repository.list_case_tool_traces(case_id)
            if trace.status == "success"
        ]
        steps = [{"tool_name": trace.tool_name, "arguments": trace.arguments} for trace in traces]
        workflow = current.repository.add_workflow(
            WorkflowTemplate(
                name=request.name,
                description=request.description,
                steps=steps,
                source_case_id=case_id,
            )
        )
        return workflow

    @app.get("/api/workflows")
    def list_workflows(current=Depends(get_state)):
        return {"workflows": [workflow.model_dump(mode="json") for workflow in current.repository.list_workflows()]}

    @app.post("/api/cases/{case_id}/workflows/{workflow_id}/run")
    def run_workflow(case_id: str, workflow_id: str, current=Depends(get_state)):
        case = current.repository.get_case(case_id)
        if case is None:
            raise HTTPException(status_code=404, detail="case not found")
        workflow = current.repository.get_workflow(workflow_id)
        if workflow is None:
            raise HTTPException(status_code=404, detail="workflow not found")
        datasets = current.repository.list_case_datasets(case_id)
        active_dataset_id = datasets[-1].id if datasets else None
        context = ToolContext(
            case_id=case_id,
            actor="workflow",
            repository=current.repository,
            case=case,
            datasets=datasets,
            active_dataset=current.repository.get_dataset(active_dataset_id) if active_dataset_id else None,
            metric_repository=current.metric_repository,
            task_queue=current.task_queue,
            generated_root=str(current.generated_root),
        )
        workflow_tool_names = {step.get("tool_name") for step in workflow.steps if isinstance(step.get("tool_name"), str)}
        selected_plugin_ids = [
            manifest.plugin_id
            for manifest in current.calibration_registry.list_manifests()
            if workflow_tool_names.intersection(manifest.tool_names)
        ]
        replay_registry = current.agent._build_active_tool_registry(
            case_id=case_id,
            actor="workflow",
            selection=CalibrationSelection(plugin_ids=selected_plugin_ids, reason="Workflow replay tool scope."),
        )
        results = []
        for step in workflow.steps:
            tool_name = step.get("tool_name")
            if not isinstance(tool_name, str):
                continue
            arguments = dict(step.get("arguments") or {})
            definition = replay_registry.get_tool(tool_name)
            if definition is not None and "dataset_id" in definition.system_injected_args:
                if active_dataset_id is None:
                    raise HTTPException(status_code=409, detail="workflow requires a dataset")
                arguments["dataset_id"] = active_dataset_id
            tool_result = replay_registry.run(tool_name, context, arguments)
            results.append({"tool_name": tool_name, "summary": tool_result.summary})
        return {"workflow": workflow, "results": results}

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

    @app.get("/api/artifacts/{artifact_id}/file")
    def get_artifact_file(artifact_id: str, current=Depends(get_state)):
        artifact = current.repository.get_artifact(artifact_id)
        if artifact is None:
            raise HTTPException(status_code=404, detail="artifact not found")
        file_path = artifact.data.get("file_path")
        if not isinstance(file_path, str) or not file_path:
            raise HTTPException(status_code=404, detail="artifact has no file")
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            raise HTTPException(status_code=404, detail="artifact file not found")
        media_type = artifact.data.get("mime_type")
        return FileResponse(
            path,
            media_type=media_type if isinstance(media_type, str) else None,
            filename=artifact.data.get("filename") if isinstance(artifact.data.get("filename"), str) else path.name,
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
        metadata = detect_file_metadata(
            filename=dataset.filename,
            content_type=file.content_type,
            content_preview=content[:4096],
        )
        dataset.log_kind = metadata.log_kind  # type: ignore[assignment]
        dataset.scenario = metadata.scenario  # type: ignore[assignment]
        dataset.matched_rule = metadata.matched_rule
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

    @app.post("/api/cases/{case_id}/messages/stream")
    def stream_message(case_id: str, request: MessageRequest, current=Depends(get_state)):
        def event_stream():
            try:
                for item in current.agent.stream_user_message(
                    case_id=case_id,
                    content=request.content,
                    dataset_id=request.dataset_id,
                ):
                    yield sse_event(item.event, item.data)
            except KeyError:
                yield sse_event("error", {"detail": "case not found", "status_code": 404})
            except LLMError as exc:
                yield sse_event("error", {"detail": str(exc), "status_code": exc.status_code})
            except Exception as exc:
                yield sse_event("error", {"detail": str(exc), "status_code": 500})

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    return app


app = create_app()


def run() -> None:
    import uvicorn

    uvicorn.run("semidiag.api.main:app", host="0.0.0.0", port=8000, reload=True)
