"""Parquet reporter: materializes columnar tables and DuckDB queries (ADR-015)."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pyarrow as pa
import pyarrow.parquet as pq

from zugzwang_core.domain.errors import PersistenceError

TABLES = ("runs", "episodes", "steps", "attempts", "events", "metric_observations")


def _normalize(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, default=str)
    return value


class ParquetReporter:
    """Materializes run tables to Parquet files queryable by DuckDB."""

    reporter_id = "reporter.parquet"
    version = "0.1.0"
    plugin_api = "zgw.plugin/v1alpha1"

    def __init__(self, rows_provider: Callable[[str, str], list[dict[str, Any]]]) -> None:
        self._rows_provider = rows_provider

    def materialize(self, run_id: str, output_dir: Path) -> dict[str, str]:
        output_dir.mkdir(parents=True, exist_ok=True)
        written: dict[str, str] = {}
        for table in TABLES:
            rows = self._rows_provider(table, run_id)
            if not rows:
                continue
            normalized = [{key: _normalize(value) for key, value in row.items()} for row in rows]
            try:
                table_data = cast(Any, pa).Table.from_pylist(normalized)
            except Exception as exc:
                raise PersistenceError(
                    f"cannot build parquet table {table}", technical_context=str(exc)
                ) from exc
            target = output_dir / f"{table}.parquet"
            cast(Any, pq).write_table(table_data, target)
            written[table] = str(target)
        return written

    def duckdb_query(self, parquet_dir: Path, query: str) -> list[dict[str, Any]]:
        import duckdb

        connection = duckdb.connect(database=":memory:")
        files = sorted(str(p) for p in parquet_dir.glob("*.parquet"))
        if not files:
            return []
        for file in files:
            table_name = Path(file).stem
            connection.execute(f"CREATE VIEW {table_name} AS SELECT * FROM read_parquet('{file}')")
        result = connection.execute(query)
        columns = [d[0] for d in result.description or []]
        return [dict(zip(columns, row, strict=False)) for row in result.fetchall()]
