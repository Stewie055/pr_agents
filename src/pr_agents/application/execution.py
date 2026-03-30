from __future__ import annotations

from pr_agents.models import (
    DatabaseAnalysisInput,
    DatabaseAnalysisRequest,
    FileAnalysisInput,
    FileAnalysisRequest,
    TaskContext,
    WorkflowResult,
)
from pr_agents.tools import WorkflowToolRegistry


class AnalysisExecutionService:
    def __init__(self, tools: WorkflowToolRegistry) -> None:
        self.tools = tools

    def run_file_analysis(self, context: TaskContext, request: FileAnalysisRequest) -> WorkflowResult:
        return self.tools.run_file_analysis(
            context,
            FileAnalysisInput(
                business_code=request.business_code,
                file_name=request.file_name,
                content=request.content,
                objective=request.objective,
                operations=request.operations,
                source_profile=request.source_profile,
                clean_profile=request.clean_profile,
                analysis_profile=request.analysis_profile,
                chart_profile=request.chart_profile,
                report_profile=request.report_profile,
            ),
        )

    def run_db_analysis(self, context: TaskContext, request: DatabaseAnalysisRequest) -> WorkflowResult:
        return self.tools.run_db_analysis(
            context,
            DatabaseAnalysisInput(
                business_code=request.business_code,
                query_name=request.query_name,
                sql=request.sql,
                objective=request.objective,
                operations=request.operations,
                source_profile=request.source_profile,
                clean_profile=request.clean_profile,
                analysis_profile=request.analysis_profile,
                chart_profile=request.chart_profile,
                report_profile=request.report_profile,
            ),
        )
