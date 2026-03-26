from pathlib import Path

from pr_agents.agent.orchestrator import UserTask
from pr_agents.bootstrap import build_app


def test_webui_facade_runs_end_to_end(tmp_path: Path) -> None:
    app = build_app(str(tmp_path))
    result = app.submit(
        UserTask(
            route="file_analysis",
            objective="prepare report",
            file_name="sample.csv",
            content="a,b\n1,2\n3,4\n",
        )
    )

    assert result.ok is True
    assert result.report is not None
    assert result.report.summary.startswith("Analysis completed")
