#!/usr/bin/env python3
"""Run the How-Real-Is-It v2 (myth-busting) pipeline on a title."""
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
from scene_sense.realism_v2.pipeline import run_hriv2_pipeline  # noqa: E402


@click.command()
@click.argument("moments_path", type=click.Path(exists=True, dir_okay=False))
@click.option("--limit", type=int, default=None)
@click.option("--domain", "domains", multiple=True, default=None)
@click.option("--verbose", is_flag=True, default=False)
def main(moments_path: str, limit: int | None, domains: tuple[str, ...], verbose: bool) -> None:
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

    summary = run_hriv2_pipeline(
        cfg=cfg, moments_path=moments_path, scene_limit=limit,
        domain_override=list(domains) if domains else None,
    )

    t = Table(title=f"How Real Is It v2: {summary.title}", show_header=True)
    t.add_column("Metric", style="cyan")
    t.add_column("Value", style="magenta")
    for k, v in [
        ("Domain", summary.domain or "-"),
        ("Scenes processed", str(summary.scenes_processed)),
        ("Myths proposed", str(summary.myths_proposed)),
        ("Myths researched", str(summary.myths_researched)),
        ("Cards generated", str(summary.cards_generated)),
        ("Cards validated", str(summary.cards_validated)),
        ("Output", summary.output_path),
    ]:
        t.add_row(k, v)
    console.print(t)


if __name__ == "__main__":
    main()
