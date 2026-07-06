"""Read historical metrics from Postgres.

Mirrors what the Analytics Service will expose at
``GET /analytics/metrics/history`` in Phase 4. Keeping the shape identical
lets us swap the transport without touching training code.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

import pandas as pd
import psycopg


METRIC_COLUMNS = [
    "service_id",
    "window_start",
    "window_end",
    "window_size",
    "request_count",
    "rpm",
    "response_time_mean",
    "response_time_p95",
    "response_time_p99",
    "error_rate",
    "success_rate",
    "cpu_usage_pct",
    "memory_usage_pct",
]


def _dsn(host: str, port: int, db: str, user: str, password: str) -> str:
    return f"host={host} port={port} dbname={db} user={user} password={password}"


def load_metrics(
    dsn: str,
    window_size: str = "1m",
    since: datetime | None = None,
    until: datetime | None = None,
) -> pd.DataFrame:
    """Load metric rows across all services in [since, until] at ``window_size``.

    ``since`` / ``until`` default to open-ended. Rows are cast to float where
    appropriate and returned as a DataFrame sorted by (service_id,
    window_start). ``service_id`` is stringified for pandas friendliness.
    """
    clauses = ["window_size = %s"]
    params: list = [window_size]
    if since is not None:
        clauses.append("window_start >= %s")
        params.append(since)
    if until is not None:
        clauses.append("window_start < %s")
        params.append(until)
    where = " AND ".join(clauses)
    sql = (
        f"SELECT {', '.join(METRIC_COLUMNS)} FROM metrics "
        f"WHERE {where} ORDER BY service_id, window_start"
    )
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    if not rows:
        return pd.DataFrame(columns=METRIC_COLUMNS)

    df = pd.DataFrame(rows, columns=METRIC_COLUMNS)
    df["service_id"] = df["service_id"].astype(str)
    df["window_start"] = pd.to_datetime(df["window_start"], utc=True)
    df["window_end"] = pd.to_datetime(df["window_end"], utc=True)
    numeric_cols = [
        "request_count",
        "rpm",
        "response_time_mean",
        "response_time_p95",
        "response_time_p99",
        "error_rate",
        "success_rate",
        "cpu_usage_pct",
        "memory_usage_pct",
    ]
    for c in numeric_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def load_metrics_for_service(
    dsn: str,
    service_id: UUID | str,
    window_size: str = "1m",
    since: datetime | None = None,
    until: datetime | None = None,
) -> pd.DataFrame:
    df = load_metrics(dsn, window_size=window_size, since=since, until=until)
    return df[df["service_id"] == str(service_id)].reset_index(drop=True)
