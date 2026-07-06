"""``synth`` CLI entrypoint.

Examples
--------
    synth generate --days 30
    synth generate --days 7 --seed 1 --out csv --path out/metrics.csv
    synth clear --since 2026-01-01
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import psycopg
import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from synthetic_data.config import settings
from synthetic_data.generator import (
    DEFAULT_PROFILES,
    default_injection_plan,
    simulate_service,
)
from synthetic_data.writer import (
    clear_synthetic_metrics,
    ensure_services,
    write_metrics,
)

app = typer.Typer(add_completion=False, help="Synthetic API telemetry generator")
console = Console()


@app.command()
def generate(
    days: int = typer.Option(30, help="Days of history to produce."),
    end: str | None = typer.Option(
        None,
        help="End timestamp (ISO-8601). Defaults to 'now (UTC) rounded down to the minute'.",
    ),
    seed: int = typer.Option(42, help="RNG seed for reproducibility."),
    out: str = typer.Option(
        "postgres",
        help="Output sink: 'postgres' or 'csv'.",
    ),
    path: Path = typer.Option(
        Path("out/metrics.csv"),
        help="Output path when --out csv.",
    ),
) -> None:
    """Produce ``days`` of one-minute-interval metric rows per default service."""
    end_dt = (
        datetime.fromisoformat(end).astimezone(UTC)
        if end
        else datetime.now(UTC).replace(second=0, microsecond=0)
    )
    start_dt = end_dt - timedelta(days=days)

    console.print(
        f"[bold]Generating[/] {days} days ({days * 24 * 60:,} minutes) × "
        f"{len(DEFAULT_PROFILES)} services "
        f"from {start_dt.isoformat()} to {end_dt.isoformat()}"
    )

    plan = default_injection_plan(DEFAULT_PROFILES, start_dt, days, seed=seed)
    console.print(
        f"[dim]Injection plan:[/] {len(plan.anomalies)} anomalies, "
        f"{len(plan.failures)} failure episodes"
    )

    frames: list[pd.DataFrame] = []
    with Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        TimeElapsedColumn(),
        transient=True,
    ) as progress:
        for prof in DEFAULT_PROFILES:
            task = progress.add_task(f"Simulating {prof.name}", total=None)
            frames.append(simulate_service(prof, start_dt, days, plan, seed))
            progress.remove_task(task)

    df = pd.concat(frames, ignore_index=True)
    console.print(f"[green]✓[/] Simulated [bold]{len(df):,}[/] rows")

    labels_df = df[["service_id", "window_start", "is_anomaly", "is_failure_window"]]
    metrics_df = df.drop(columns=["is_anomaly", "is_failure_window"])

    if out == "csv":
        path.parent.mkdir(parents=True, exist_ok=True)
        metrics_df.to_csv(path, index=False)
        labels_path = path.with_name(path.stem + ".labels.csv")
        labels_df.to_csv(labels_path, index=False)
        console.print(f"[green]✓[/] Wrote metrics → {path}")
        console.print(f"[green]✓[/] Wrote labels  → {labels_path}")
        return

    if out != "postgres":
        raise typer.BadParameter(f"unknown --out {out!r} (expected postgres or csv)")

    with psycopg.connect(settings.dsn) as conn:
        console.print("[dim]Ensuring service registry entries...")
        ensure_services(conn, DEFAULT_PROFILES)

        console.print("[dim]Bulk-copying metrics to Postgres...")
        written = write_metrics(conn, metrics_df)
        console.print(f"[green]✓[/] Wrote [bold]{written:,}[/] rows to metrics table")

        # Persist ground-truth labels alongside for evaluation.
        labels_path = Path("out/labels.csv")
        labels_path.parent.mkdir(parents=True, exist_ok=True)
        labels_df.to_csv(labels_path, index=False)
        console.print(f"[green]✓[/] Wrote ground-truth labels → {labels_path}")


@app.command()
def clear(
    since: str = typer.Option(
        ...,
        help="ISO-8601 date/datetime; delete synthetic metric rows from this point onward.",
    ),
) -> None:
    """Delete synthetic rows (owner='synthetic') from the metrics table."""
    since_dt = datetime.fromisoformat(since)
    if since_dt.tzinfo is None:
        since_dt = since_dt.replace(tzinfo=UTC)
    with psycopg.connect(settings.dsn) as conn:
        removed = clear_synthetic_metrics(conn, since_dt)
    console.print(f"[green]✓[/] Removed [bold]{removed:,}[/] synthetic metric rows")


if __name__ == "__main__":
    app()
