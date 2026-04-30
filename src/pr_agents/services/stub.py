from __future__ import annotations

from html import escape
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
    SourcePattern,
    TaskContext,
)
from pr_agents.services.base import AnalysisPlatform


class StubAnalysisPlatform(AnalysisPlatform):
    """Minimal deterministic implementation for tests and scaffolding."""

    def __init__(self, artifact_store: ArtifactStore | None = None) -> None:
        self.artifact_store = artifact_store or ArtifactStore()

    def parse_file(
        self,
        context: TaskContext,
        file_name: str,
        content: str,
        business_code: str,
        source_profile: dict,
    ) -> DatasetRef:
        rows = [line for line in content.splitlines() if line.strip()]
        columns = rows[0].split(",") if rows else []
        source_pattern = source_profile.get("source_pattern", SourcePattern.PER_BUSINESS_FILE.value)
        if source_pattern == SourcePattern.SHARED_FILE.value and rows:
            business_rows = [rows[0]]
            for row in rows[1:]:
                if row.split(",")[0] == business_code:
                    business_rows.append(row)
            if len(business_rows) == 1:
                raise ValueError(f"no rows found for business_code={business_code}")
            rows = business_rows
            content = "\n".join(rows) + "\n"
        artifact = self.artifact_store.save_text(
            context,
            ArtifactType.TABLE,
            f"{business_code}_dataset_from_file.csv",
            content,
        )
        return DatasetRef(
            dataset_id=f"dataset-{uuid4().hex[:8]}",
            source_type=DataSourceType.FILE,
            source_uri=file_name,
            columns=columns,
            row_count=max(len(rows) - 1, 0),
            artifact=artifact,
            metadata={
                "ingested_from": "file",
                "business_code": business_code,
                "source_pattern": source_pattern,
                "source_mode": DataSourceType.FILE.value,
                "data_version": source_profile.get("data_version", "stub-v1"),
            },
        )

    def query_database(
        self,
        context: TaskContext,
        query_name: str,
        sql: str,
        business_code: str,
        source_profile: dict,
    ) -> DatasetRef:
        content = f"business_code,category,value\n{business_code},A,10\n{business_code},B,20\n"
        artifact = self.artifact_store.save_text(
            context,
            ArtifactType.TABLE,
            f"{business_code}_dataset_from_db.csv",
            content,
        )
        return DatasetRef(
            dataset_id=f"dataset-{uuid4().hex[:8]}",
            source_type=DataSourceType.DATABASE,
            source_uri=query_name,
            columns=["business_code", "category", "value"],
            row_count=2,
            artifact=artifact,
            metadata={
                "sql": sql,
                "business_code": business_code,
                "source_pattern": source_profile.get("source_pattern", SourcePattern.SHARED_FILE.value),
                "source_mode": DataSourceType.DATABASE.value,
                "data_version": source_profile.get("data_version", "stub-v1"),
            },
        )

    def clean_data(
        self,
        context: TaskContext,
        dataset: DatasetRef,
        operations: list[str],
        business_code: str,
        clean_profile: dict,
    ) -> DatasetRef:
        dataset.metadata["clean_operations"] = operations
        dataset.metadata["cleaned"] = True
        dataset.metadata["business_code"] = business_code
        dataset.metadata["clean_stage"] = clean_profile.get("clean_stage", "standardized")
        dataset.metadata["clean_profile"] = clean_profile
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
                f"Business code: {request.business_code}",
                f"Objective: {request.objective}",
                f"Operations: {', '.join(request.operations) or 'none'}",
            ],
            dataset_id=dataset.dataset_id,
            metadata={
                "business_code": request.business_code,
                "analysis_kind": request.analysis_profile.get("analysis_kind", "stub_analysis"),
                "model_name": request.analysis_profile.get("model_name", "stub_model"),
                "thresholds": request.analysis_profile.get("thresholds", {}),
            },
        )

    def build_chart(
        self,
        context: TaskContext,
        dataset: DatasetRef,
        analysis: AnalysisResult,
        request: AnalysisRequest,
    ) -> ChartArtifact:
        chart_type = request.chart_profile.get("chart_type", "bar")
        series = [10, 20, 16]
        labels = ["Input", "Model", "Report"]
        max_value = max(series)
        svg_bars = []
        for index, value in enumerate(series):
            height = int((value / max_value) * 170)
            x = 70 + index * 120
            y = 230 - height
            svg_bars.append(
                f'<rect x="{x}" y="{y}" width="64" height="{height}" rx="14" fill="#1f6feb" opacity="{0.92 - index * 0.1:.2f}" />'
            )
            svg_bars.append(
                f'<text x="{x + 32}" y="252" text-anchor="middle" font-size="13" fill="#334155">{escape(labels[index])}</text>'
            )
            svg_bars.append(
                f'<text x="{x + 32}" y="{y - 10}" text-anchor="middle" font-size="12" fill="#0f172a">{value}</text>'
            )
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="480" height="280" viewBox="0 0 480 280">'
            '<defs><linearGradient id="bg" x1="0%" x2="100%" y1="0%" y2="100%">'
            '<stop offset="0%" stop-color="#eff6ff" /><stop offset="100%" stop-color="#dbeafe" />'
            "</linearGradient></defs>"
            '<rect width="480" height="280" rx="24" fill="url(#bg)" />'
            '<text x="32" y="42" font-size="20" font-family="Arial, sans-serif" fill="#0f172a">'
            f'{escape(request.business_code)} {escape(chart_type)}</text>'
            '<text x="32" y="68" font-size="13" font-family="Arial, sans-serif" fill="#475569">'
            f'{escape(analysis.summary)}</text>'
            '<line x1="52" y1="230" x2="432" y2="230" stroke="#94a3b8" stroke-width="2" />'
            + "".join(svg_bars)
            + "</svg>"
        )
        artifact = self.artifact_store.save_text(
            context,
            ArtifactType.CHART_IMAGE,
            f"{request.business_code}_{chart_type}.svg",
            svg,
        )
        return ChartArtifact(
            chart_id=f"chart-{uuid4().hex[:8]}",
            title=f"Chart for {dataset.dataset_id}",
            chart_type=chart_type,
            artifact=artifact,
            config={
                "objective": request.objective,
                "summary": analysis.summary,
                "business_code": request.business_code,
                "plot_family": "scientific" if chart_type == "scientific_plot" else "standard",
                "chart_profile": request.chart_profile,
                "series": series,
                "labels": labels,
            },
        )

    def generate_report(
        self,
        context: TaskContext,
        dataset: DatasetRef | None,
        analysis: AnalysisResult,
        chart: ChartArtifact | None,
        request: AnalysisRequest,
    ) -> ReportArtifact:
        data_quality = (
            f"- Rows: {dataset.row_count if dataset else 0}\n"
            f"- Columns: {', '.join(dataset.columns) if dataset and dataset.columns else 'n/a'}\n"
            "- Missing values: not detected in stub profile"
        )
        findings = "\n".join(f"- {insight}" for insight in analysis.insights)
        artifact_refs = [
            f"- Chart: {chart.artifact.artifact_id}" if chart else "- Chart: n/a",
            f"- Table: {dataset.artifact.artifact_id}" if dataset and dataset.artifact else "- Table: n/a",
        ]
        artifact = self.artifact_store.save_text(
            context,
            ArtifactType.REPORT,
            f"{request.business_code}_report.md",
            "\n".join(
                [
                    f"# {request.objective}",
                    "",
                    "## 摘要",
                    f"business_code={request.business_code}",
                    analysis.summary,
                    "",
                    "## 数据质量",
                    data_quality,
                    "",
                    "## 关键发现",
                    findings,
                    "",
                    "## 建议",
                    "- Use the generated chart as a first-pass diagnostic view.",
                    "- Replace the stub adapter with the target QT business adapter for production use.",
                    "",
                    "## 产物引用",
                    *artifact_refs,
                ]
            ),
        )
        dataset_id = dataset.dataset_id if dataset else analysis.dataset_id or "unknown"
        return ReportArtifact(
            report_id=f"report-{uuid4().hex[:8]}",
            title=f"Report for {dataset_id}",
            artifact=artifact,
            sections=["summary", "data_quality", "findings", "recommendations", "artifacts"],
            summary=analysis.summary,
        )
