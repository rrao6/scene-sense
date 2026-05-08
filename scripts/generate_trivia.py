#!/usr/bin/env python3
"""Run the trivia pipeline on a Tubi Moments JSON file."""
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
from scene_sense.trivia.pipeline import run_trivia_pipeline  # noqa: E402


@click.command()
@click.argument("moments_path", type=click.Path(exists=True, dir_okay=False))
@click.option("--limit", type=int, default=None, help="Only process the first N eligible scenes.")
@click.option("--topics", "topic_count", type=int, default=6, help="Topics to propose per scene (oversupply for ranking).")
@click.option("--fame-min", type=int, default=3, help="Min subject fame score (1-5) to pass fame gate.")
@click.option("--verbose", is_flag=True, default=False)
def main(moments_path: str, limit: int | None, topic_count: int, fame_min: int, verbose: bool) -> None:
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

    summary = run_trivia_pipeline(
        cfg=cfg, moments_path=moments_path, scene_limit=limit,
        topic_count=topic_count, fame_min_score=fame_min,
    )

    table = Table(title=f"Trivia pipeline: {summary.title}", show_header=True)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="magenta")
    rows = [
        ("Scenes processed", str(summary.scenes_processed)),
        ("Topics proposed", str(summary.topics_proposed)),
        ("  after scene-overlap veto", str(summary.topics_after_scene_veto)),
        ("  after fame gate", str(summary.topics_after_fame_gate)),
        ("Sources grounded", str(summary.sources_grounded)),
        ("Prompts generated", str(summary.prompts_generated)),
        ("Prompts validator-passed", str(summary.prompts_validated)),
        ("Output", summary.output_path),
    ]
    for k, v in rows:
        table.add_row(k, v)
    console.print(table)


if __name__ == "__main__":
    main()
