"""``python -m app.training.cli`` — train all or a subset of the ML modules.

Reads historical metrics from Postgres (or in Phase 4 from the Analytics
Service HTTP endpoint), engineers features, trains, evaluates, and
persists each model artifact to ``$ML_MODEL_DIR``.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Callable

import typer
from rich.console import Console
from rich.table import Table

from app.clients.metrics import load_metrics
from app.config import settings
from app.modules.alerts.train import train as train_alerts
from app.modules.anomaly.train import train as train_anomaly
from app.modules.failure.train import train as train_failure
from app.modules.traffic.train import train as train_traffic

app = typer.Typer(add_completion=False, help="ML model training CLI")
console = Console()

TRAINERS: dict[str, Callable] = {
    "traffic": train_traffic,
    "failure": train_failure,
    "anomaly": train_anomaly,
    "alerts": train_alerts,
    # "health" has no learned model — it's a deterministic weighted score.
}


@app.command()
def train(
    modules: list[str] = typer.Option(
        None,
        "--module",
        "-m",
        help="Subset to train. Repeatable. Omit to train all learnable modules.",
    ),
    days: int = typer.Option(30, help="History window (days) used for training."),
    model_dir: Path = typer.Option(
        None,
        help="Override ML_MODEL_DIR from env. Directory is created if missing.",
    ),
) -> None:
    """Train models. Artifacts persist under ``model_dir``."""
    target_modules = modules or list(TRAINERS.keys())
    unknown = [m for m in target_modules if m not in TRAINERS]
    if unknown:
        raise typer.BadParameter(
            f"unknown module(s): {unknown}. Valid: {list(TRAINERS.keys())}"
        )

    out_dir = model_dir or settings.model_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    console.print(f"[bold]Model output dir:[/] {out_dir}")

    end = datetime.now(UTC).replace(second=0, microsecond=0)
    start = end - timedelta(days=days)
    console.print(f"[bold]Loading metrics[/] from {start.isoformat()} .. {end.isoformat()}")

    df = load_metrics(settings.pg_dsn, window_size="1m", since=start, until=end)
    if df.empty:
        console.print("[red]No metrics found. Run the synthetic-data generator first.[/]")
        raise typer.Exit(code=1)
    console.print(f"[green]✓[/] Loaded [bold]{len(df):,}[/] rows across "
                  f"{df['service_id'].nunique()} services")

    results: list[dict] = []
    for name in target_modules:
        console.rule(f"[bold cyan]{name}")
        result = TRAINERS[name](df, out_dir)
        results.append({"module": name, **result})

    _print_summary(results)


def _print_summary(results: list[dict]) -> None:
    if not results:
        return
    table = Table(title="Training summary")
    table.add_column("Module", style="cyan")
    table.add_column("Version", style="dim")
    table.add_column("Rows", justify="right")
    table.add_column("Metrics")
    for r in results:
        metrics = ", ".join(f"{k}={v:.4f}" for k, v in r.get("metrics", {}).items())
        table.add_row(
            r["module"],
            r.get("model_version", "-"),
            f"{r.get('training_rows', 0):,}",
            metrics or "-",
        )
    console.print(table)


if __name__ == "__main__":
    app()
