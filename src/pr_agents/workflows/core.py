from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, TypeVar

from pr_agents.models import (
    AnalysisRequest,
    DatabaseAnalysisInput,
    FileAnalysisInput,
    ReportGenerationInput,
    WorkflowError,
    WorkflowResult,
)
from pr_agents.services import AnalysisPlatform

T = TypeVar("T")


@dataclass
class WorkflowBase:
    platform: AnalysisPlatform

    def _execute_step(self, step: str, operation: Callable[[], T], result: WorkflowResult) -> T | None:
        try:
            return operation()
        except Exception as exc:  # pragma: no cover - behavior asserted through result
            result.errors.append(
                WorkflowError(code="workflow_step_failed", message=str(exc), step=step)
            )
            return None


class FileAnalysisWorkflow(WorkflowBase):
    def run(self, context, payload: FileAnalysisInput) -> WorkflowResult:
        result = WorkflowResult(context=context)
        request = AnalysisRequest(
            business_code=payload.business_code,
            objective=payload.objective,
            operations=payload.operations,
            source_mode=payload.source_mode,
            source_profile=payload.source_profile,
            clean_profile=payload.clean_profile,
            analysis_profile=payload.analysis_profile,
            chart_profile=payload.chart_profile,
            report_profile=payload.report_profile,
        )

        dataset = self._execute_step(
            "parse_file",
            lambda: self.platform.parse_file(
                context,
                payload.file_name,
                payload.content,
                payload.business_code,
                payload.source_profile,
            ),
            result,
        )
        if not dataset:
            return result

        result.dataset = self._execute_step(
            "clean_data",
            lambda: self.platform.clean_data(
                context,
                dataset,
                payload.operations,
                payload.business_code,
                payload.clean_profile,
            ),
            result,
        )
        if not result.dataset:
            return result

        result.analysis = self._execute_step(
            "analyze_data",
            lambda: self.platform.analyze_data(context, result.dataset, request),
            result,
        )
        if not result.analysis:
            return result

        result.chart = self._execute_step(
            "build_chart",
            lambda: self.platform.build_chart(context, result.dataset, result.analysis, request),
            result,
        )
        if not result.chart:
            return result

        result.report = self._execute_step(
            "generate_report",
            lambda: self.platform.generate_report(
                context, result.dataset, result.analysis, result.chart, request
            ),
            result,
        )
        result.artifacts = [
            artifact
            for artifact in [
                result.dataset.artifact if result.dataset else None,
                result.chart.artifact if result.chart else None,
                result.report.artifact if result.report else None,
            ]
            if artifact is not None
        ]
        return result


class DatabaseAnalysisWorkflow(WorkflowBase):
    def run(self, context, payload: DatabaseAnalysisInput) -> WorkflowResult:
        result = WorkflowResult(context=context)
        request = AnalysisRequest(
            business_code=payload.business_code,
            objective=payload.objective,
            operations=payload.operations,
            source_mode=payload.source_mode,
            source_profile=payload.source_profile,
            clean_profile=payload.clean_profile,
            analysis_profile=payload.analysis_profile,
            chart_profile=payload.chart_profile,
            report_profile=payload.report_profile,
        )

        dataset = self._execute_step(
            "query_database",
            lambda: self.platform.query_database(
                context,
                payload.query_name,
                payload.sql,
                payload.business_code,
                payload.source_profile,
            ),
            result,
        )
        if not dataset:
            return result

        result.dataset = self._execute_step(
            "clean_data",
            lambda: self.platform.clean_data(
                context,
                dataset,
                payload.operations,
                payload.business_code,
                payload.clean_profile,
            ),
            result,
        )
        if not result.dataset:
            return result

        result.analysis = self._execute_step(
            "analyze_data",
            lambda: self.platform.analyze_data(context, result.dataset, request),
            result,
        )
        if not result.analysis:
            return result

        result.chart = self._execute_step(
            "build_chart",
            lambda: self.platform.build_chart(context, result.dataset, result.analysis, request),
            result,
        )
        if not result.chart:
            return result

        result.report = self._execute_step(
            "generate_report",
            lambda: self.platform.generate_report(
                context, result.dataset, result.analysis, result.chart, request
            ),
            result,
        )
        result.artifacts = [
            artifact
            for artifact in [
                result.dataset.artifact if result.dataset else None,
                result.chart.artifact if result.chart else None,
                result.report.artifact if result.report else None,
            ]
            if artifact is not None
        ]
        return result


class ReportFromExistingArtifactsWorkflow(WorkflowBase):
    def run(self, context, payload: ReportGenerationInput) -> WorkflowResult:
        result = WorkflowResult(
            context=context,
            dataset=payload.dataset,
            analysis=payload.analysis,
            chart=payload.chart,
        )
        request = AnalysisRequest(
            business_code=payload.business_code,
            objective=payload.objective,
            dataset_id=payload.dataset.dataset_id if payload.dataset else payload.analysis.dataset_id,
            operations=["report"],
            report_profile=payload.report_profile,
            analysis_profile=payload.analysis.metadata,
        )
        result.report = self._execute_step(
            "generate_report",
            lambda: self.platform.generate_report(
                context,
                payload.dataset,
                payload.analysis,
                payload.chart,
                request,
            ),
            result,
        )
        result.artifacts = [
            artifact
            for artifact in [
                payload.dataset.artifact if payload.dataset else None,
                payload.chart.artifact if payload.chart else None,
                result.report.artifact if result.report else None,
            ]
            if artifact is not None
        ]
        return result
