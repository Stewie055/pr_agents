from pathlib import Path

from pr_agents.infrastructure import ArtifactStore
from pr_agents.models import AnalysisRequest, SourcePattern, TaskContext
from pr_agents.services import StubAnalysisPlatform


def test_stub_platform_generates_dataset_chart_and_report(tmp_path: Path) -> None:
    platform = StubAnalysisPlatform(ArtifactStore(str(tmp_path)))
    context = TaskContext(user_request="analyze sample", workspace=str(tmp_path))
    dataset = platform.parse_file(
        context,
        "sample.csv",
        "a,b\n1,2\n",
        "A001",
        {"source_pattern": SourcePattern.PER_BUSINESS_FILE.value},
    )
    dataset = platform.clean_data(context, dataset, ["clean"], "A001", {"clean_stage": "ready"})
    analysis = platform.analyze_data(
        context,
        dataset,
        AnalysisRequest(
            business_code="A001",
            objective="analyze sample",
            operations=["clean", "analyze"],
        ),
    )
    chart = platform.build_chart(
        context,
        dataset,
        analysis,
        AnalysisRequest(
            business_code="A001",
            objective="analyze sample",
            operations=["visualize"],
            chart_profile={"chart_type": "scientific_plot"},
        ),
    )
    report = platform.generate_report(
        context,
        dataset,
        analysis,
        chart,
        AnalysisRequest(
            business_code="A001",
            objective="analyze sample",
            operations=["report"],
        ),
    )

    assert dataset.metadata["cleaned"] is True
    assert dataset.metadata["business_code"] == "A001"
    assert chart.chart_type == "scientific_plot"
    assert chart.artifact.uri.endswith("A001_scientific_plot.json")
    assert report.artifact.uri.endswith("A001_report.md")


def test_stub_platform_filters_shared_file_by_business_code(tmp_path: Path) -> None:
    platform = StubAnalysisPlatform(ArtifactStore(str(tmp_path)))
    context = TaskContext(user_request="analyze shared file", workspace=str(tmp_path))
    dataset = platform.parse_file(
        context,
        "shared.csv",
        "business_code,value\nB001,1\nB002,2\nB001,3\n",
        "B001",
        {"source_pattern": SourcePattern.SHARED_FILE.value},
    )

    assert dataset.row_count == 2
    assert dataset.metadata["source_pattern"] == SourcePattern.SHARED_FILE.value
