from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from pr_agents.application.tasks import TaskApplicationService
from pr_agents.infrastructure import AgentSessionRepository
from pr_agents.models import (
    AgentMessage,
    AgentSessionResponse,
    AgentUserMessageRequest,
    CreateAgentSessionResponse,
    DatabaseAnalysisRequest,
    FileAnalysisRequest,
    MessageRole,
    MessageType,
)


class AgentSessionService:
    def __init__(
        self,
        session_repository: AgentSessionRepository,
        task_service: TaskApplicationService,
        demo_data_path: str,
    ) -> None:
        self.session_repository = session_repository
        self.task_service = task_service
        self.demo_data_path = Path(demo_data_path)

    def create_session(self) -> CreateAgentSessionResponse:
        session_id = f"session-{uuid4().hex[:8]}"
        self.session_repository.create_session(session_id)
        self.session_repository.add_message(
            session_id,
            MessageRole.ASSISTANT,
            MessageType.CHAT,
            "Agent session created. Ask me to analyze demo data, generate charts, or produce a report.",
        )
        return CreateAgentSessionResponse(session_id=session_id)

    def get_session(self, session_id: str) -> AgentSessionResponse:
        self.session_repository.create_session(session_id)
        return AgentSessionResponse(
            session_id=session_id,
            messages=self.session_repository.list_messages(session_id),
            tasks=self.task_service.list_session_tasks(session_id),
        )

    def handle_message(self, session_id: str, request: AgentUserMessageRequest) -> AgentSessionResponse:
        self.session_repository.create_session(session_id)
        self.session_repository.add_message(
            session_id,
            MessageRole.USER,
            MessageType.CHAT,
            request.content,
        )

        if self._is_report_follow_up(request.content):
            self._append_report_follow_up(session_id)
            return self.get_session(session_id)

        use_database = self._wants_database(request.content)
        business_code = self._extract_business_code(request.content)
        objective = self._build_objective(request.content, business_code)

        self.session_repository.add_message(
            session_id,
            MessageRole.ASSISTANT,
            MessageType.PLAN,
            (
                f"I will use {'database' if use_database else 'file'} analysis for {business_code}, "
                "generate a scientific plot, and return a report."
            ),
            metadata={"business_code": business_code, "entry": "database" if use_database else "file"},
        )

        tool_name = "run_db_analysis" if use_database else "run_file_analysis"
        self.session_repository.add_message(
            session_id,
            MessageRole.TOOL,
            MessageType.TOOL_CALL,
            tool_name,
            metadata={"business_code": business_code},
        )

        if use_database:
            task_response = self.task_service.submit_db_analysis(
                DatabaseAnalysisRequest(
                    business_code=business_code,
                    objective=objective,
                    query_name="demo_query",
                    sql="select * from cleaned_demo_data",
                    source_profile={"source_pattern": "shared_file", "data_version": "demo-v1"},
                    chart_profile={"chart_type": "scientific_plot"},
                    report_profile={"template": "demo-template"},
                    session_id=session_id,
                )
            )
        else:
            task_response = self.task_service.submit_file_analysis(
                FileAnalysisRequest(
                    business_code=business_code,
                    objective=objective,
                    file_name=self.demo_data_path.name,
                    content=self.demo_data_path.read_text(encoding="utf-8"),
                    source_profile={"source_pattern": "per_business_file", "data_version": "demo-v1"},
                    chart_profile={"chart_type": "scientific_plot"},
                    report_profile={"template": "demo-template"},
                    session_id=session_id,
                )
            )

        if task_response.error:
            self.session_repository.add_message(
                session_id,
                MessageRole.ASSISTANT,
                MessageType.ERROR,
                task_response.error.message,
                metadata={"task_id": task_response.task_id},
            )
            return self.get_session(session_id)

        result = task_response.result
        report_text = ""
        report_artifact_id = None
        if result and result.report:
            report_artifact_id = result.report.artifact.artifact_id
            report_text = self.task_service.read_artifact_content(report_artifact_id) or ""

        self.session_repository.add_message(
            session_id,
            MessageRole.TOOL,
            MessageType.TOOL_RESULT,
            f"Task {task_response.task_id} finished with status {task_response.status.value}.",
            metadata={
                "task_id": task_response.task_id,
                "session_id": task_response.session_id,
                "chart_type": result.chart.chart_type if result and result.chart else None,
                "report_artifact_id": report_artifact_id,
            },
        )
        self.session_repository.add_message(
            session_id,
            MessageRole.ASSISTANT,
            MessageType.CHAT,
            (
                f"Completed {business_code}. "
                f"Chart type: {result.chart.chart_type if result and result.chart else 'n/a'}. "
                f"Report summary: {result.report.summary if result and result.report else 'n/a'}.\n\n"
                f"{report_text}"
            ),
            metadata={
                "task_id": task_response.task_id,
                "report_artifact_id": report_artifact_id,
                "business_code": business_code,
            },
        )
        return self.get_session(session_id)

    def read_session_artifact_content(self, session_id: str, artifact_id: str) -> str | None:
        task_ids = {task.task_id for task in self.task_service.list_session_tasks(session_id)}
        artifact = self.task_service.get_artifact(artifact_id)
        if artifact is None or artifact.task_id not in task_ids:
            return None
        return self.task_service.read_artifact_content(artifact_id)

    def _append_report_follow_up(self, session_id: str) -> None:
        tasks = self.task_service.list_session_tasks(session_id)
        if not tasks:
            self.session_repository.add_message(
                session_id,
                MessageRole.ASSISTANT,
                MessageType.ERROR,
                "There is no completed task in this session yet. Run the demo first.",
            )
            return
        latest_task = tasks[-1]
        detail = self.task_service.get_task(latest_task.task_id)
        if detail is None:
            self.session_repository.add_message(
                session_id,
                MessageRole.ASSISTANT,
                MessageType.ERROR,
                "I could not load the latest task details.",
            )
            return
        report_artifact = next((a for a in detail.artifacts if a.artifact_type.value == "report"), None)
        if report_artifact is None:
            self.session_repository.add_message(
                session_id,
                MessageRole.ASSISTANT,
                MessageType.ERROR,
                "The latest task does not have a report artifact.",
            )
            return
        report_text = self.task_service.read_artifact_content(report_artifact.artifact_id) or ""
        self.session_repository.add_message(
            session_id,
            MessageRole.ASSISTANT,
            MessageType.CHAT,
            report_text,
            metadata={"task_id": latest_task.task_id, "report_artifact_id": report_artifact.artifact_id},
        )

    @staticmethod
    def _extract_business_code(content: str) -> str:
        upper = content.upper()
        if "A_DEMO" in upper:
            return "A_DEMO"
        if "B001" in upper:
            return "B001"
        return "A_DEMO"

    @staticmethod
    def _wants_database(content: str) -> bool:
        normalized = content.lower()
        return "database" in normalized or "数据库" in content

    @staticmethod
    def _is_report_follow_up(content: str) -> bool:
        normalized = content.lower()
        return (
            "show me the report again" in normalized
            or "show the report again" in normalized
            or "report again" in normalized
            or "再看报告" in content
            or "重新看报告" in content
        )

    @staticmethod
    def _build_objective(content: str, business_code: str) -> str:
        if content.strip():
            return content.strip()
        return f"Generate a scientific plot report for {business_code}"
