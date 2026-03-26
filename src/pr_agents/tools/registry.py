from __future__ import annotations

from pydantic import BaseModel

from pr_agents.models import (
    AnalysisRequest,
    ChartArtifact,
    DatabaseAnalysisInput,
    DatasetRef,
    FileAnalysisInput,
    ReportArtifact,
    ReportGenerationInput,
    TaskContext,
    WorkflowResult,
)
from pr_agents.workflows import (
    DatabaseAnalysisWorkflow,
    FileAnalysisWorkflow,
    ReportFromExistingArtifactsWorkflow,
)


class GenerateChartInput(BaseModel):
    dataset: DatasetRef
    request: AnalysisRequest


class GenerateReportInput(BaseModel):
    payload: ReportGenerationInput


class WorkflowToolRegistry:
    def __init__(
        self,
        file_workflow: FileAnalysisWorkflow,
        database_workflow: DatabaseAnalysisWorkflow,
        report_workflow: ReportFromExistingArtifactsWorkflow,
    ) -> None:
        self.file_workflow = file_workflow
        self.database_workflow = database_workflow
        self.report_workflow = report_workflow
        self.platform = file_workflow.platform

    def run_file_analysis(self, context: TaskContext, payload: FileAnalysisInput) -> WorkflowResult:
        return self.file_workflow.run(context, payload)

    def run_db_analysis(self, context: TaskContext, payload: DatabaseAnalysisInput) -> WorkflowResult:
        return self.database_workflow.run(context, payload)

    def describe_dataset(self, context: TaskContext, dataset: DatasetRef) -> dict:
        return {
            "dataset_id": dataset.dataset_id,
            "source_type": dataset.source_type.value,
            "row_count": dataset.row_count,
            "columns": dataset.columns,
            "metadata": dataset.metadata,
        }

    def generate_chart(self, context: TaskContext, payload: GenerateChartInput) -> ChartArtifact:
        analysis = self.platform.analyze_data(context, payload.dataset, payload.request)
        return self.platform.build_chart(context, payload.dataset, analysis, payload.request)

    def generate_report(self, context: TaskContext, payload: GenerateReportInput) -> ReportArtifact:
        result = self.report_workflow.run(context, payload.payload)
        if result.errors or not result.report:
            error = result.errors[0] if result.errors else None
            raise RuntimeError(error.message if error else "report generation failed")
        return result.report
