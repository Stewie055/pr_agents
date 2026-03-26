from __future__ import annotations

from uuid import uuid4

from pr_agents.infrastructure import ArtifactStore
from pr_agents.models import (
    AnalysisRequest,
    AnalysisResult,
    ArtifactType,
    ChartArtifact,
    DataSourceType,
    DatasetRef,
    MetricResult,
    ReportArtifact,
    TaskContext,
)
from pr_agents.services.base import AnalysisPlatform


class StubAnalysisPlatform(AnalysisPlatform):
    """Minimal deterministic implementation for tests and scaffolding."""

    def __init__(self, artifact_store: ArtifactStore | None = None) -> None:
        self.artifact_store = artifact_store or ArtifactStore()

    def parse_file(self, context: TaskContext, file_name: str, content: str) -> DatasetRef:
        rows = [line for line in content.splitlines() if line.strip()]
        columns = rows[0].split(",") if rows else []
        artifact = self.artifact_store.save_text(
            context,
            ArtifactType.DATASET,
            "dataset_from_file.csv",
            content,
        )
        return DatasetRef(
            dataset_id=f"dataset-{uuid4().hex[:8]}",
            source_type=DataSourceType.FILE,
            source_uri=file_name,
            columns=columns,
            row_count=max(len(rows) - 1, 0),
            artifact=artifact,
            metadata={"ingested_from": "file"},
        )

    def query_database(self, context: TaskContext, query_name: str, sql: str) -> DatasetRef:
        content = "category,value\nA,10\nB,20\n"
        artifact = self.artifact_store.save_text(
            context,
            ArtifactType.DATASET,
            "dataset_from_db.csv",
            content,
        )
        return DatasetRef(
            dataset_id=f"dataset-{uuid4().hex[:8]}",
            source_type=DataSourceType.DATABASE,
            source_uri=query_name,
            columns=["category", "value"],
            row_count=2,
            artifact=artifact,
            metadata={"sql": sql},
        )

    def clean_data(self, context: TaskContext, dataset: DatasetRef, operations: list[str]) -> DatasetRef:
        dataset.metadata["clean_operations"] = operations
        dataset.metadata["cleaned"] = True
        return dataset

    def analyze_data(
        self,
        context: TaskContext,
        dataset: DatasetRef,
        request: AnalysisRequest,
    ) -> AnalysisResult:
        return AnalysisResult(
            summary=f"Analysis completed for {dataset.dataset_id}",
            metrics=[
                MetricResult(name="row_count", value=dataset.row_count),
                MetricResult(name="column_count", value=len(dataset.columns)),
            ],
            insights=[
                f"Objective: {request.objective}",
                f"Operations: {', '.join(request.operations) or 'none'}",
            ],
            dataset_id=dataset.dataset_id,
        )

    def build_chart(
        self,
        context: TaskContext,
        dataset: DatasetRef,
        analysis: AnalysisResult,
        request: AnalysisRequest,
    ) -> ChartArtifact:
        artifact = self.artifact_store.save_text(
            context,
            ArtifactType.CHART,
            "chart.json",
            '{"type":"bar","series":[10,20]}',
        )
        return ChartArtifact(
            chart_id=f"chart-{uuid4().hex[:8]}",
            title=f"Chart for {dataset.dataset_id}",
            chart_type="bar",
            artifact=artifact,
            config={"objective": request.objective, "summary": analysis.summary},
        )

    def generate_report(
        self,
        context: TaskContext,
        dataset: DatasetRef | None,
        analysis: AnalysisResult,
        chart: ChartArtifact | None,
        request: AnalysisRequest,
    ) -> ReportArtifact:
        artifact = self.artifact_store.save_text(
            context,
            ArtifactType.REPORT,
            "report.md",
            "\n".join(
                [
                    f"# {request.objective}",
                    analysis.summary,
                    *(analysis.insights or []),
                ]
            ),
        )
        dataset_id = dataset.dataset_id if dataset else analysis.dataset_id or "unknown"
        return ReportArtifact(
            report_id=f"report-{uuid4().hex[:8]}",
            title=f"Report for {dataset_id}",
            artifact=artifact,
            sections=["summary", "insights"],
            summary=analysis.summary,
        )
