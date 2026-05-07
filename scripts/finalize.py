#!/usr/bin/env python3
"""Consolidate all generator outputs for a title into final + review JSONs.

Usage:
    python scripts/finalize.py --title "The Devils Advocate" \
        --moments data/samples/The_Devils_Advocate.json \
        --outputs data/outputs/the_devils_advocate.tier0.json \
                  data/outputs/the_devils_advocate.trivia.json \
                  data/outputs/the_devils_advocate.realism.json
"""
from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scene_sense.eval.finalize import finalize_title  # noqa: E402


@click.command()
@click.option("--title", required=True)
@click.option("--moments", required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--outputs", "outputs", multiple=True, required=True, type=click.Path(exists=False, dir_okay=False))
@click.option("--with-eval/--no-eval", default=True, help="Re-fetch every source and verify claims (slower).")
def main(title: str, moments: str, outputs: tuple[str, ...], with_eval: bool) -> None:
    console = Console()
    console.print(f"Finalizing {title}  (eval={'on' if with_eval else 'off'})")
    result = finalize_title(
        title=title,
        moments_path=moments,
        output_dir=REPO_ROOT / "data" / "outputs",
        generator_outputs=[Path(o) for o in outputs],
        run_eval=with_eval,
    )
    t = Table(title=f"Finalize: {result.title}", show_header=True)
    t.add_column("Metric", style="cyan")
    t.add_column("Value", style="magenta")
    t.add_row("Total prompts (after dedup)", str(result.total_prompts))
    t.add_row("Dedup removed", str(result.dedup_removed))
    t.add_row("Per primitive", ", ".join(f"{k}:{v}" for k, v in result.per_primitive.items()))
    t.add_row("Per verdict", ", ".join(f"{k}:{v}" for k, v in result.per_verdict.items()))
    t.add_row("Overall avg score", str(result.overall_avg))
    t.add_row("Final JSON (full audit)", result.final_path)
    t.add_row("Review JSON (detailed)", result.review_path)
    t.add_row("Cards JSON (slim)", result.cards_json_path)
    t.add_row("Cards Markdown (HITL)", result.cards_md_path)
    t.add_row("UI bundle (client contract)", result.ui_path)
    console.print(t)


if __name__ == "__main__":
    main()
