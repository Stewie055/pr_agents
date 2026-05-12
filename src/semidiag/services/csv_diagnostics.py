from __future__ import annotations

import csv
import math
import re
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt
from pptx import Presentation
from pptx.util import Inches, Pt

from semidiag.domain import AnalysisArtifact, DiagnosisConclusion, Evidence
from semidiag.vendor.ppt_template_sdk import ImageContent, PptTemplateEngine, RenderContext, RendererRegistry, TextContent


class CSVDiagnosticService:
    """Demo service for semiconductor equipment performance files.

    Real projects should replace this with device-specific diagnostic packages.
    """

    def __init__(self, generated_root: Path | str = "var/generated") -> None:
        self.generated_root = Path(generated_root)

    def parse_dataset(self, *, case_id: str, dataset_id: str, path: str) -> AnalysisArtifact:
        rows = self._read_rows(path)
        columns = list(rows[0].keys()) if rows else []
        return AnalysisArtifact(
            case_id=case_id,
            kind="dataset",
            title="Parsed equipment performance dataset",
            summary=f"Parsed {len(rows)} rows and {len(columns)} columns.",
            source_file_id=dataset_id,
            data={"rows": rows[:100], "row_count": len(rows), "columns": columns},
        )

    def inspect_dataset(self, *, case_id: str, dataset_id: str, path: str) -> AnalysisArtifact:
        rows = self._read_rows(path)
        columns = list(rows[0].keys()) if rows else []
        numeric = self._numeric_columns(rows)
        column_types = {column: ("numeric" if column in numeric else "text") for column in columns}
        preview = rows[:5]
        return AnalysisArtifact(
            case_id=case_id,
            kind="table",
            title="Dataset schema and preview",
            summary=f"Inspected {len(rows)} rows and {len(columns)} columns.",
            source_file_id=dataset_id,
            data={
                "columns": columns,
                "column_types": column_types,
                "numeric_columns": list(numeric.keys()),
                "row_count": len(rows),
                "preview": preview,
            },
        )

    def profile_dataset(self, *, case_id: str, dataset_id: str, path: str) -> tuple[AnalysisArtifact, list[Evidence]]:
        rows = self._read_rows(path)
        numeric = self._numeric_columns(rows)
        profile: dict[str, Any] = {}
        evidence: list[Evidence] = []

        for column, values in numeric.items():
            if not values:
                continue
            avg = mean(values)
            sigma = pstdev(values) if len(values) > 1 else 0.0
            profile[column] = {
                "count": len(values),
                "mean": avg,
                "min": min(values),
                "max": max(values),
                "stddev": sigma,
            }
            if sigma > abs(avg) * 0.25 and sigma > 0:
                evidence.append(
                    Evidence(
                        case_id=case_id,
                        title=f"{column} variance is elevated",
                        evidence_type="metric",
                        summary=f"{column} stddev is {sigma:.3f}, which is high relative to mean {avg:.3f}.",
                        data={"column": column, "mean": avg, "stddev": sigma},
                    )
                )

            outliers = [value for value in values if sigma and abs(value - avg) > 3 * sigma]
            if outliers:
                evidence.append(
                    Evidence(
                        case_id=case_id,
                        title=f"{column} has outlier samples",
                        evidence_type="metric",
                        summary=f"Detected {len(outliers)} samples outside three standard deviations.",
                        data={"column": column, "outliers": outliers[:10]},
                    )
                )

        artifact = AnalysisArtifact(
            case_id=case_id,
            kind="table",
            title="Performance metric profile",
            summary=f"Profiled {len(profile)} numeric equipment metrics.",
            source_file_id=dataset_id,
            data={"profile": profile},
        )
        return artifact, evidence

    def build_chart(self, *, case_id: str, dataset_id: str, path: str) -> list[AnalysisArtifact]:
        rows = self._read_rows(path)
        numeric = self._numeric_columns(rows)
        columns = list(numeric.keys())[:8]
        if not columns:
            return [
                AnalysisArtifact(
                    case_id=case_id,
                    kind="chart",
                    title="Performance chart unavailable",
                    summary="No numeric metric columns were found for plotting.",
                    source_file_id=dataset_id,
                    data={"render_type": "none", "series": []},
                )
            ]

        artifacts: list[AnalysisArtifact] = []
        case_dir = self._case_generated_dir(case_id) / "charts"
        case_dir.mkdir(parents=True, exist_ok=True)

        overview_columns = columns[: min(4, len(columns))]
        overview_path = case_dir / "performance_trend_overview.png"
        self._save_line_chart(
            output_path=overview_path,
            series={column: numeric[column][:200] for column in overview_columns},
            title="Performance Trend Overview",
            ylabel="normalized value",
            normalize=True,
        )
        artifacts.append(
            self._chart_artifact(
                case_id=case_id,
                dataset_id=dataset_id,
                title="Performance trend overview",
                summary=f"Generated Matplotlib overview trend for {len(overview_columns)} numeric metric(s).",
                file_path=overview_path,
                figure_kind="trend_overview",
                display_group="Trend",
                order=0,
                series_names=overview_columns,
                point_count=max((len(numeric[column][:200]) for column in overview_columns), default=0),
            )
        )

        for index, column in enumerate(columns, start=1):
            metric_path = case_dir / f"{self._safe_filename(column)}_trend.png"
            self._save_line_chart(
                output_path=metric_path,
                series={column: numeric[column][:200]},
                title=f"{column} Trend",
                ylabel=column,
                normalize=False,
            )
            values = numeric[column]
            artifacts.append(
                self._chart_artifact(
                    case_id=case_id,
                    dataset_id=dataset_id,
                    title=f"{column} trend",
                    summary=f"Generated Matplotlib trend plot for {column}.",
                    file_path=metric_path,
                    figure_kind="metric_trend",
                    display_group="Metric Trend",
                    order=index,
                    series_names=[column],
                    point_count=len(values[:200]),
                    extra={"min": min(values), "max": max(values), "mean": mean(values)},
                )
            )

        return artifacts

    def diagnose(
        self,
        *,
        case_id: str,
        profile_artifact: AnalysisArtifact,
        evidence: list[Evidence],
    ) -> tuple[AnalysisArtifact, DiagnosisConclusion]:
        profile = profile_artifact.data.get("profile", {})
        causes: list[str] = []
        recommendations: list[str] = []
        risk = "low"
        confidence = 0.45

        if evidence:
            risk = "medium"
            confidence = 0.7
            causes.append("Process or equipment drift indicated by unstable performance metrics.")
            recommendations.append("Review recent maintenance, recipe changes, and environmental logs around the outlier windows.")
        if any("temperature" in key.lower() for key in profile):
            causes.append("Thermal control loop should be reviewed because temperature metrics are present in the anomaly set.")
            recommendations.append("Compare chamber temperature trend against control limits and cooling subsystem events.")
        if not causes:
            causes.append("No strong abnormal pattern was detected in the demo rules.")
            recommendations.append("Run device-specific diagnostic package before issuing a formal conclusion.")

        conclusion = DiagnosisConclusion(
            case_id=case_id,
            title="Preliminary equipment performance diagnosis",
            possible_causes=causes,
            confidence=confidence,
            risk_level=risk,  # type: ignore[arg-type]
            recommendations=recommendations,
            evidence_ids=[item.id for item in evidence],
        )
        artifact = AnalysisArtifact(
            case_id=case_id,
            kind="diagnosis",
            title=conclusion.title,
            summary=f"{risk.title()} risk preliminary diagnosis with {len(evidence)} evidence item(s).",
            data=conclusion.model_dump(mode="json"),
        )
        return artifact, conclusion

    def generate_report(
        self,
        *,
        case_id: str,
        artifacts: list[AnalysisArtifact],
        evidence: list[Evidence],
    ) -> AnalysisArtifact:
        sections = [
            {
                "heading": "Executive Summary",
                "body": "This diagnostic report was generated from structured artifacts, Matplotlib charts, and evidence.",
            },
            {
                "heading": "Evidence",
                "body": "\n".join(f"- {item.title}: {item.summary}" for item in evidence) or "No evidence generated.",
            },
            {
                "heading": "Artifacts",
                "body": "\n".join(f"- {item.title}: {item.summary}" for item in artifacts),
            },
            {
                "heading": "Review Requirement",
                "body": "Formal diagnosis and recommendations require authorized engineer review before release.",
            },
        ]
        report_dir = self._case_generated_dir(case_id) / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        chart_artifacts = [
            item
            for item in artifacts
            if item.kind == "chart" and isinstance(item.data.get("file_path"), str) and Path(str(item.data["file_path"])).exists()
        ]
        report_path = report_dir / f"diagnostic_report_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.pptx"
        renderer = self._render_ppt_report(
            output_path=report_path,
            case_id=case_id,
            sections=sections,
            artifacts=artifacts,
            evidence=evidence,
            chart_artifacts=chart_artifacts,
        )

        artifact = AnalysisArtifact(
            case_id=case_id,
            kind="report",
            title="Diagnostic report deck",
            summary="Generated an editable PPTX diagnostic report for engineer review.",
            data={
                "format": "pptx",
                "mime_type": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                "filename": report_path.name,
                "file_path": str(report_path),
                "sections": sections,
                "chart_count": len(chart_artifacts),
                "template_engine": renderer,
            },
        )
        artifact.data["file_url"] = f"/api/artifacts/{artifact.id}/file"
        return artifact

    def _case_generated_dir(self, case_id: str) -> Path:
        path = self.generated_root / case_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _safe_filename(self, value: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())[:80]
        return cleaned or "metric"

    def _save_line_chart(
        self,
        *,
        output_path: Path,
        series: dict[str, list[float]],
        title: str,
        ylabel: str,
        normalize: bool,
    ) -> None:
        fig, ax = plt.subplots(figsize=(10, 5.2), dpi=140)
        for name, values in series.items():
            y_values = values
            if normalize and values:
                min_value = min(values)
                max_value = max(values)
                spread = max_value - min_value
                y_values = [(value - min_value) / spread if spread else 0.0 for value in values]
            ax.plot(range(len(y_values)), y_values, linewidth=1.8, marker="o", markersize=2.5, label=name)
        ax.set_title(title)
        ax.set_xlabel("sample index")
        ax.set_ylabel(ylabel)
        ax.grid(True, alpha=0.25)
        ax.legend(loc="best", fontsize=8)
        fig.tight_layout()
        fig.savefig(output_path, format="png")
        plt.close(fig)

    def _chart_artifact(
        self,
        *,
        case_id: str,
        dataset_id: str,
        title: str,
        summary: str,
        file_path: Path,
        figure_kind: str,
        display_group: str,
        order: int,
        series_names: list[str],
        point_count: int,
        extra: dict[str, Any] | None = None,
    ) -> AnalysisArtifact:
        artifact = AnalysisArtifact(
            case_id=case_id,
            kind="chart",
            title=title,
            summary=summary,
            source_file_id=dataset_id,
            data={
                "render_type": "image",
                "mime_type": "image/png",
                "filename": file_path.name,
                "file_path": str(file_path),
                "figure_kind": figure_kind,
                "display_group": display_group,
                "order": order,
                "series_names": series_names,
                "point_count": point_count,
                "source_metrics": series_names,
                **(extra or {}),
            },
        )
        artifact.data["file_url"] = f"/api/artifacts/{artifact.id}/file"
        return artifact

    def _render_ppt_report(
        self,
        *,
        output_path: Path,
        case_id: str,
        sections: list[dict[str, str]],
        artifacts: list[AnalysisArtifact],
        evidence: list[Evidence],
        chart_artifacts: list[AnalysisArtifact],
    ) -> str:
        template_path = output_path.with_name("diagnostic_report_template.pptx")
        self._create_default_template(template_path, include_chart=bool(chart_artifacts))
        registry = RendererRegistry()

        @registry.renderer("title")
        def render_title(placeholder, context):
            return TextContent(text=context.get_value("title", "Diagnostic Report"))

        @registry.renderer("subtitle")
        def render_subtitle(placeholder, context):
            return TextContent(text=context.get_value("subtitle", "Semiconductor equipment performance diagnosis"))

        @registry.renderer("summary")
        def render_summary(placeholder, context):
            return TextContent(text=context.get_value("summary", ""))

        @registry.renderer("evidence")
        def render_evidence(placeholder, context):
            return TextContent(text=context.get_value("evidence_text", "No evidence generated."))

        @registry.renderer("artifacts")
        def render_artifacts(placeholder, context):
            return TextContent(text=context.get_value("artifact_text", "No artifacts generated."))

        if chart_artifacts:

            @registry.renderer("primary_chart")
            def render_primary_chart(placeholder, context):
                return ImageContent(image_path=context.get_value("primary_chart_path"))

        context = RenderContext(
            data={
                "title": "Diagnostic Report",
                "subtitle": "Engineer review draft",
                "summary": sections[0]["body"],
                "evidence_text": "\n".join(f"- {item.title}: {item.summary}" for item in evidence)
                or "No evidence generated.",
                "artifact_text": "\n".join(f"- {item.title}: {item.summary}" for item in artifacts)
                or "No artifacts generated.",
                "primary_chart_path": str(chart_artifacts[0].data["file_path"]) if chart_artifacts else "",
            }
        )
        PptTemplateEngine(registry=registry).render(
            template_path=str(template_path),
            output_path=str(output_path),
            context=context,
        )
        return "ppt_template_sdk"

    def _create_default_template(self, path: Path, *, include_chart: bool) -> None:
        presentation = Presentation()
        presentation.slide_width = Inches(13.333)
        presentation.slide_height = Inches(7.5)

        title_slide = presentation.slides.add_slide(presentation.slide_layouts[6])
        title_box = title_slide.shapes.add_textbox(Inches(0.7), Inches(1.7), Inches(11.8), Inches(0.8))
        title_box.name = "ph:text:title"
        title_box.text_frame.text = "Diagnostic Report"
        title_box.text_frame.paragraphs[0].font.size = Pt(34)
        subtitle_box = title_slide.shapes.add_textbox(Inches(0.75), Inches(2.75), Inches(11.2), Inches(0.6))
        subtitle_box.name = "ph:text:subtitle"
        subtitle_box.text_frame.text = "Semiconductor equipment performance diagnosis"

        summary_slide = presentation.slides.add_slide(presentation.slide_layouts[6])
        heading = summary_slide.shapes.add_textbox(Inches(0.6), Inches(0.45), Inches(12), Inches(0.45))
        heading.text_frame.text = "Executive Summary"
        body = summary_slide.shapes.add_textbox(Inches(0.7), Inches(1.2), Inches(11.8), Inches(4.9))
        body.name = "ph:text:summary"
        body.text_frame.text = "Summary"

        evidence_slide = presentation.slides.add_slide(presentation.slide_layouts[6])
        heading = evidence_slide.shapes.add_textbox(Inches(0.6), Inches(0.45), Inches(12), Inches(0.45))
        heading.text_frame.text = "Evidence And Artifacts"
        evidence_box = evidence_slide.shapes.add_textbox(Inches(0.7), Inches(1.15), Inches(5.8), Inches(5.5))
        evidence_box.name = "ph:text:evidence"
        evidence_box.text_frame.text = "Evidence"
        artifact_box = evidence_slide.shapes.add_textbox(Inches(6.8), Inches(1.15), Inches(5.8), Inches(5.5))
        artifact_box.name = "ph:text:artifacts"
        artifact_box.text_frame.text = "Artifacts"

        if include_chart:
            chart_slide = presentation.slides.add_slide(presentation.slide_layouts[6])
            heading = chart_slide.shapes.add_textbox(Inches(0.6), Inches(0.45), Inches(12), Inches(0.45))
            heading.text_frame.text = "Primary Trend Chart"
            chart_box = chart_slide.shapes.add_textbox(Inches(0.85), Inches(1.05), Inches(11.6), Inches(5.95))
            chart_box.name = "ph:image:primary_chart"
            chart_box.text_frame.text = "Chart"

        presentation.save(path)

    def _read_rows(self, path: str) -> list[dict[str, str]]:
        with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))

    def _numeric_columns(self, rows: list[dict[str, str]]) -> dict[str, list[float]]:
        values: dict[str, list[float]] = {}
        for row in rows:
            for key, raw in row.items():
                try:
                    value = float(raw)
                except (TypeError, ValueError):
                    continue
                if math.isfinite(value):
                    values.setdefault(key, []).append(value)
        return values
