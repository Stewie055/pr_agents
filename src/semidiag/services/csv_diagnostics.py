from __future__ import annotations

import csv
import math
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

from semidiag.domain import AnalysisArtifact, DiagnosisConclusion, Evidence


class CSVDiagnosticService:
    """Demo service for semiconductor equipment performance files.

    Real projects should replace this with device-specific diagnostic packages.
    """

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

    def build_chart(self, *, case_id: str, dataset_id: str, path: str) -> AnalysisArtifact:
        rows = self._read_rows(path)
        numeric = self._numeric_columns(rows)
        columns = list(numeric.keys())[:3]
        series = [{"name": column, "values": numeric[column][:80]} for column in columns]
        return AnalysisArtifact(
            case_id=case_id,
            kind="chart",
            title="Performance trend preview",
            summary="Generated line-series chart data for the first numeric metrics.",
            source_file_id=dataset_id,
            data={"type": "line", "x": list(range(max((len(item["values"]) for item in series), default=0))), "series": series},
        )

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
                "body": "This is a draft diagnostic report generated from structured artifacts and evidence.",
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
        return AnalysisArtifact(
            case_id=case_id,
            kind="report",
            title="Editable diagnostic report draft",
            summary="Generated a structured report draft for engineer review.",
            data={"format": "structured_markdown", "sections": sections},
        )

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
