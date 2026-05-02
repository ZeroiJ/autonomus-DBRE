from __future__ import annotations

import os
import sys
from importlib import metadata
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from dbre.database import DBREPostgres
from dbre.inference import ModelLoadError, default_adapter_dir, load_optimizer_model
from dbre.optimizer import optimize_sql
from dbre.procedural_workload import ProceduralWorkloadGenerator


def _version_string() -> str:
    try:
        return metadata.version("autonomic-dbre")
    except metadata.PackageNotFoundError:
        return "0.1.0-dev"


@click.group()
@click.version_option(version=_version_string(), prog_name="dbre")
def main() -> None:
    """Autonomic DBRE — optimize PostgreSQL queries with a trained Qwen + LoRA adapter."""


@main.command("version")
def cmd_version() -> None:
    """Print package and Python version."""
    click.echo(f"dbre {_version_string()} (Python {sys.version.split()[0]})")


@main.command("status")
@click.option(
    "--adapter-path",
    type=click.Path(path_type=Path),
    default=None,
    help="Directory with adapter_config.json (default: dbre_trained or DBRE_ADAPTER_DIR)",
)
def cmd_status(adapter_path: Path | None) -> None:
    """Check database connectivity and adapter files."""
    ap = Path(adapter_path) if adapter_path else default_adapter_dir()
    cfg = ap / "adapter_config.json"

    click.echo("Autonomic DBRE status")
    click.echo("-" * 40)
    click.echo(f"Adapter path:  {ap}")
    click.echo(f"adapter_config.json: {'yes' if cfg.is_file() else 'NO (train or download weights)'}")

    os.environ.setdefault("DB_USER", "dbre_admin")
    os.environ.setdefault("DB_PASSWORD", "dbre_pass")
    os.environ.setdefault("DB_HOST", "localhost")
    os.environ.setdefault("DB_PORT", "5432")
    os.environ.setdefault("DB_NAME", "dbre")

    try:
        db = DBREPostgres()
        db.connect()
        db.conn.close()
        click.echo("PostgreSQL:    connected")
    except Exception as e:
        click.echo(f"PostgreSQL:    FAILED ({e})")

    if cfg.is_file():
        click.echo("Adapter:       adapter_config.json found (run `dbre optimize` to load the full model)")
    else:
        click.echo("Adapter:       not found — train with train.py or set --adapter-path")


@main.command("sample-broken")
@click.option("--seed", default=42, help="RNG seed for procedural generation.")
def cmd_sample_broken(seed: int) -> None:
    """Print one procedurally generated broken query (hard mode) and exit."""
    os.environ.setdefault("DB_USER", "dbre_admin")
    os.environ.setdefault("DB_PASSWORD", "dbre_pass")
    os.environ.setdefault("DB_HOST", "localhost")
    os.environ.setdefault("DB_PORT", "5432")
    os.environ.setdefault("DB_NAME", "dbre")

    db = DBREPostgres()
    try:
        db.connect()
        db.create_tables()
    except Exception as e:
        raise click.ClickException(f"Database connection failed: {e}") from e

    wl = ProceduralWorkloadGenerator(db.conn, seed=seed)
    try:
        sql, lat = wl.generate_broken_query()
    finally:
        db.conn.close()
    click.echo(sql)
    click.echo(f"-- baseline_latency_ms ~ {lat:.2f}", err=True)


@main.command("optimize")
@click.argument("query", type=str)
@click.option(
    "--explain",
    is_flag=True,
    help="Print full EXPLAIN (ANALYZE, BUFFERS) for the optimized query.",
)
@click.option(
    "--adapter-path",
    type=click.Path(path_type=Path),
    default=None,
    help="LoRA adapter directory (default: dbre_trained)",
)
@click.option(
    "--seed",
    is_flag=True,
    help="Drop and reseed the demo database (destructive).",
)
def cmd_optimize(
    query: str,
    explain: bool,
    adapter_path: Path | None,
    seed: bool,
) -> None:
    """Rewrite SQL for speed; compares latency and EXPLAIN plans."""
    os.environ.setdefault("DB_USER", "dbre_admin")
    os.environ.setdefault("DB_PASSWORD", "dbre_pass")
    os.environ.setdefault("DB_HOST", "localhost")
    os.environ.setdefault("DB_PORT", "5432")
    os.environ.setdefault("DB_NAME", "dbre")

    ap = Path(adapter_path) if adapter_path else default_adapter_dir()

    db = DBREPostgres()
    try:
        db.connect()
    except Exception as e:
        raise click.ClickException(f"Database connection failed: {e}") from e

    try:
        db.create_tables()
        if seed:
            db.seed_data()
    except Exception as e:
        db.conn.close()
        raise click.ClickException(f"Database setup failed: {e}") from e

    click.echo("Loading Qwen2.5-Coder + LoRA adapter (first run may download weights)...")
    try:
        model, tokenizer = load_optimizer_model(ap)
    except ModelLoadError as e:
        db.conn.close()
        raise click.ClickException(str(e)) from e

    try:
        outcome = optimize_sql(
            db.conn,
            query,
            model,
            tokenizer,
            include_explain_text=explain,
        )
    finally:
        db.conn.close()

    if outcome.error:
        raise click.ClickException(outcome.error)

    console = Console()
    tbl = Table(title="SQL optimization", show_header=True, header_style="bold cyan")
    tbl.add_column("Field", style="dim")
    tbl.add_column("Value")

    tbl.add_row("Original query", outcome.original)
    tbl.add_row("Optimized query", outcome.optimized)
    tbl.add_row("Latency before (ms)", f"{outcome.baseline_latency_ms:.4f}")
    tbl.add_row("Latency after (ms)", f"{outcome.optimized_latency_ms:.4f}")
    tbl.add_row("Improvement %", f"{outcome.improvement_pct:+.2f}%")
    tbl.add_row("EXPLAIN summary", outcome.explain_summary)
    rb = outcome.reward_breakdown
    tbl.add_row(
        "Rewards",
        f"c={rb.get('correctness', 0):.3f} e={rb.get('efficiency', 0):.3f} "
        f"s={rb.get('style', 0):.3f} a={rb.get('anticheat', 0):.3f} total={rb.get('total', 0):.3f}",
    )
    console.print(tbl)

    if explain and outcome.explain_full:
        console.print("\n[bold]Full EXPLAIN (ANALYZE)[/bold]")
        console.print(outcome.explain_full)


if __name__ == "__main__":
    main()
