from __future__ import annotations

from semidiag.infrastructure.metrics import MetricPoint, SQLiteMetricRepository


def test_sqlite_metric_repository_replaces_dataset_points(tmp_path):
    repository = SQLiteMetricRepository(tmp_path / "metrics.sqlite3")
    first = [
        MetricPoint(case_id="case_1", dataset_id="ds_1", metric_name="temperature", sample_index=0, value=70.0),
        MetricPoint(case_id="case_1", dataset_id="ds_1", metric_name="temperature", sample_index=1, value=71.0),
    ]
    second = [
        MetricPoint(case_id="case_1", dataset_id="ds_1", metric_name="pressure", sample_index=0, value=10.0),
    ]

    assert repository.replace_dataset_points("ds_1", first) == 2
    assert repository.replace_dataset_points("ds_1", second) == 1

    points = repository.list_dataset_points("ds_1")
    assert points == second
