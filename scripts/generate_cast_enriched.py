#!/usr/bin/env python3
"""Enrich VLM-detected cast with real career facts — generates actorFact cards."""
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

from scene_sense.cast_enrichment.pipeline import run_cast_enrichment  # noqa: E402
from scene_sense.realism.config import load_config  # noqa: E402


@click.command()
@click.argument("moments_path", type=click.Path(exists=True, dir_okay=False))
@click.option("--max-actors", type=int, default=12)
def main(moments_path: str, max_actors: int) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    console = Console()
    cfg = load_config(REPO_ROOT / ".env")
    cfg.cache_dir = REPO_ROOT / cfg.cache_dir
    cfg.outputs_dir = REPO_ROOT / cfg.outputs_dir
    cfg.source_bank_dir = REPO_ROOT / cfg.source_bank_dir
    cfg.ensure_dirs()

    summary = run_cast_enrichment(cfg=cfg, moments_path=moments_path, max_actors=max_actors)
    t = Table(title=f"Cast enrichment: {summary.title}", show_header=True)
    t.add_column("Metric", style="cyan")
    t.add_column("Value", style="magenta")
    for k, v in [
        ("Actors considered", str(summary.actors_considered)),
        ("Actors enriched", str(summary.actors_enriched)),
        ("Output", summary.output_path),
    ]:
        t.add_row(k, v)
    console.print(t)


if __name__ == "__main__":
    main()
