from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel


class MetricPoint(BaseModel):
    case_id: str
    dataset_id: str
    metric_name: str
    sample_index: int
    value: float


class MetricRepository(Protocol):
    def replace_dataset_points(self, dataset_id: str, points: Iterable[MetricPoint]) -> int:
        raise NotImplementedError

    def list_dataset_points(self, dataset_id: str) -> list[MetricPoint]:
        raise NotImplementedError


class SQLiteMetricRepository:
    """Local metric repository with the same write contract expected from ClickHouse adapters."""

    def __init__(self, db_path: Path | str = "var/metrics.sqlite3") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                create table if not exists metric_points (
                    case_id text not null,
                    dataset_id text not null,
                    metric_name text not null,
                    sample_index integer not null,
                    value real not null,
                    primary key (dataset_id, metric_name, sample_index)
                );
                create index if not exists idx_metric_points_case_dataset
                on metric_points(case_id, dataset_id);
                """
            )

    def replace_dataset_points(self, dataset_id: str, points: Iterable[MetricPoint]) -> int:
        buffered = list(points)
        with self._connect() as conn:
            conn.execute("delete from metric_points where dataset_id = ?", (dataset_id,))
            conn.executemany(
                """
                insert into metric_points(case_id, dataset_id, metric_name, sample_index, value)
                values (?, ?, ?, ?, ?)
                """,
                [
                    (point.case_id, point.dataset_id, point.metric_name, point.sample_index, point.value)
                    for point in buffered
                ],
            )
        return len(buffered)

    def list_dataset_points(self, dataset_id: str) -> list[MetricPoint]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                select case_id, dataset_id, metric_name, sample_index, value
                from metric_points
                where dataset_id = ?
                order by metric_name asc, sample_index asc
                """,
                (dataset_id,),
            ).fetchall()
        return [MetricPoint.model_validate(dict(row)) for row in rows]
