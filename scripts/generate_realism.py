#!/usr/bin/env python3
"""Run the How-Real-Is-It pipeline on a Tubi Moments JSON file.

Usage:
    python scripts/generate_realism.py data/samples/The_Devils_Advocate.json
    python scripts/generate_realism.py data/samples/The_Devils_Advocate.json --limit 8
    python scripts/generate_realism.py ... --domain legal --domain religious
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scene_sense.realism.config import load_config  # noqa: E402
from scene_sense.realism.pipeline import run_pipeline  # noqa: E402


@click.command()
@click.argument("moments_path", type=click.Path(exists=True, dir_okay=False))
@click.option("--limit", type=int, default=None, help="Only process the first N eligible scenes.")
@click.option("--domain", "domains", multiple=True, default=None, help="Override domain detection (repeatable).")
@click.option("--verbose", is_flag=True, default=False, help="Debug logging.")
def main(moments_path: str, limit: int | None, domains: tuple[str, ...], verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    console = Console()
    cfg = load_config(REPO_ROOT / ".env")
    # rebase cache/outputs relative to repo root so CLI is cwd-agnostic
    cfg.cache_dir = REPO_ROOT / cfg.cache_dir
    cfg.outputs_dir = REPO_ROOT / cfg.outputs_dir
    cfg.source_bank_dir = REPO_ROOT / cfg.source_bank_dir
    cfg.ensure_dirs()

    domain_override = list(domains) if domains else None
    summary = run_pipeline(
        cfg=cfg,
        moments_path=moments_path,
        scene_limit=limit,
        domain_override=domain_override,
    )

    table = Table(title=f"Realism pipeline: {summary.title}", show_header=True)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="magenta")
    rows = [
        ("Domains", ", ".join(summary.domains) or "-"),
        ("Content scenes", str(summary.total_content_scenes)),
        ("Scenes processed", str(summary.scenes_processed)),
        ("Claims extracted", str(summary.total_claims)),
        ("Claims bound to sources", str(summary.claims_bound)),
        ("Prompts generated", str(summary.prompts_generated)),
        ("Prompts validator-passed", str(summary.prompts_validated)),
        ("Source banks", ", ".join(f"{k}:{v}" for k, v in summary.per_domain_source_counts.items()) or "-"),
        ("Output", summary.output_path),
    ]
    for k, v in rows:
        table.add_row(k, v)
    console.print(table)


if __name__ == "__main__":
    main()
