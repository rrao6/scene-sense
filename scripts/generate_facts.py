#!/usr/bin/env python3
"""Generate editorial BTS Fact cards for a title."""
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

from scene_sense.facts.pipeline import run_facts_pipeline  # noqa: E402
from scene_sense.realism.config import load_config  # noqa: E402


@click.command()
@click.argument("moments_path", type=click.Path(exists=True, dir_okay=False))
@click.option("--topics", "topic_limit", type=int, default=None)
@click.option("--verbose", is_flag=True, default=False)
def main(moments_path: str, topic_limit: int | None, verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    console = Console()
    cfg = load_config(REPO_ROOT / ".env")
    cfg.cache_dir = REPO_ROOT / cfg.cache_dir
    cfg.outputs_dir = REPO_ROOT / cfg.outputs_dir
    cfg.source_bank_dir = REPO_ROOT / cfg.source_bank_dir
    cfg.ensure_dirs()

    summary = run_facts_pipeline(cfg=cfg, moments_path=moments_path, topic_limit=topic_limit)

    table = Table(title=f"Facts pipeline: {summary.title}", show_header=True)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="magenta")
    rows = [
        ("Topics proposed", str(summary.total_topics)),
        ("Topics with sources", str(summary.topics_with_sources)),
        ("Cards generated", str(summary.cards_generated)),
        ("Cards validator-passed", str(summary.cards_validated)),
        ("Output", summary.output_path),
    ]
    for k, v in rows:
        table.add_row(k, v)
    console.print(table)


if __name__ == "__main__":
    main()
