from pathlib import Path

from pr_agents.infrastructure import ArtifactStore
from pr_agents.models import AnalysisRequest, TaskContext
from pr_agents.services import StubAnalysisPlatform


def test_stub_platform_generates_dataset_chart_and_report(tmp_path: Path) -> None:
    platform = StubAnalysisPlatform(ArtifactStore(str(tmp_path)))
    context = TaskContext(user_request="analyze sample", workspace=str(tmp_path))
    dataset = platform.parse_file(context, "sample.csv", "a,b\n1,2\n")
    dataset = platform.clean_data(context, dataset, ["clean"])
    analysis = platform.analyze_data(
        context,
        dataset,
        AnalysisRequest(objective="analyze sample", operations=["clean", "analyze"]),
    )
    chart = platform.build_chart(
        context,
        dataset,
        analysis,
        AnalysisRequest(objective="analyze sample", operations=["visualize"]),
    )
    report = platform.generate_report(
        context,
        dataset,
        analysis,
        chart,
        AnalysisRequest(objective="analyze sample", operations=["report"]),
    )

    assert dataset.metadata["cleaned"] is True
    assert chart.artifact.uri.endswith("chart.json")
    assert report.artifact.uri.endswith("report.md")
