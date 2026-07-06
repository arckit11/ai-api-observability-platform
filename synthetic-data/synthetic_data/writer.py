"""Postgres writer.

Bulk-inserts synthetic ``metrics`` rows with ``COPY`` for speed. Also
registers services in the ``services`` table if they don't exist yet, so
FK constraints hold.
"""
from __future__ import annotations

import io
from datetime import datetime

import pandas as pd
import psycopg

from synthetic_data.generator import ServiceProfile


def ensure_services(conn: psycopg.Connection, profiles: list[ServiceProfile]) -> None:
    with conn.cursor() as cur:
        for p in profiles:
            cur.execute(
                """
                INSERT INTO services (id, name, base_url, owner, environment,
                                      description, capture_telemetry)
                VALUES (%s, %s, %s, %s, %s, %s, TRUE)
                ON CONFLICT (id) DO NOTHING
                """,
                (
                    str(p.service_id),
                    p.name,
                    f"http://{p.name}.internal",
                    "synthetic",
                    "development",
                    "Synthetic service registered by the data generator.",
                ),
            )
    conn.commit()


def write_metrics(conn: psycopg.Connection, df: pd.DataFrame, chunk_rows: int = 20_000) -> int:
    """Bulk-copy metrics rows into Postgres. Returns count written."""
    total = 0
    cols = [
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
    ]
    with conn.cursor() as cur:
        # metrics has a UNIQUE (service_id, window_size, window_start) constraint;
        # COPY doesn't honour ON CONFLICT so we route through a temp table and
        # do an upsert-style INSERT ... ON CONFLICT DO NOTHING.
        cur.execute(
            """
            CREATE TEMP TABLE _stage_metrics
              (LIKE metrics INCLUDING DEFAULTS)
              ON COMMIT DROP
            """
        )
        for chunk_start in range(0, len(df), chunk_rows):
            chunk = df.iloc[chunk_start : chunk_start + chunk_rows]
            buf = io.StringIO()
            chunk[cols].to_csv(buf, header=False, index=False, na_rep="\\N")
            buf.seek(0)
            with cur.copy(
                f"COPY _stage_metrics ({', '.join(cols)}) FROM STDIN WITH (FORMAT csv, NULL '\\N')"
            ) as copy:
                copy.write(buf.read())
            total += len(chunk)
        cur.execute(
            f"""
            INSERT INTO metrics ({', '.join(cols)})
            SELECT {', '.join(cols)} FROM _stage_metrics
            ON CONFLICT (service_id, window_size, window_start) DO NOTHING
            """
        )
    conn.commit()
    return total


def clear_synthetic_metrics(conn: psycopg.Connection, since: datetime) -> int:
    """Remove synthetic metric rows on or after ``since``. Only affects services
    with owner='synthetic' so we never touch real production data."""
    with conn.cursor() as cur:
        cur.execute(
            """
            DELETE FROM metrics
            WHERE service_id IN (SELECT id FROM services WHERE owner = 'synthetic')
              AND window_start >= %s
            RETURNING 1
            """,
            (since,),
        )
        removed = cur.rowcount
    conn.commit()
    return removed
