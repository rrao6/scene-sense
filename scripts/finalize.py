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
@click.option("--with-judge/--no-judge", default=False, help="Run the LLM curiosity judge (adds ~1s/card, significant quality lift).")
@click.option("--cap-trivia", type=int, default=None, help="Keep only top N trivia by score.")
@click.option("--cap-facts", type=int, default=None, help="Keep only top N facts by score.")
@click.option("--cap-hriv2", type=int, default=None, help="Keep only top N how_real_is_it by score.")
@click.option("--cap-scene-iq", type=int, default=None, help="Keep only top N scene_iq by score.")
@click.option("--cap-cast", type=int, default=None, help="Keep only top N cast by score.")
def main(title: str, moments: str, outputs: tuple[str, ...], with_eval: bool, with_judge: bool,
         cap_trivia: int | None, cap_facts: int | None, cap_hriv2: int | None,
         cap_scene_iq: int | None, cap_cast: int | None) -> None:
    import sys as _sys
    _src = REPO_ROOT / "src"
    if str(_src) not in _sys.path:
        _sys.path.insert(0, str(_src))
    from scene_sense.realism.config import load_config

    cfg = load_config(REPO_ROOT / ".env") if with_judge else None
    if cfg is not None:
        cfg.cache_dir = REPO_ROOT / cfg.cache_dir
        cfg.outputs_dir = REPO_ROOT / cfg.outputs_dir
        cfg.source_bank_dir = REPO_ROOT / cfg.source_bank_dir
        cfg.ensure_dirs()
    rank_caps = {}
    if cap_trivia is not None: rank_caps["trivia"] = cap_trivia
    if cap_facts is not None: rank_caps["facts"] = cap_facts
    if cap_hriv2 is not None: rank_caps["how_real_is_it"] = cap_hriv2
    if cap_scene_iq is not None: rank_caps["scene_iq"] = cap_scene_iq
    if cap_cast is not None: rank_caps["cast"] = cap_cast

    console = Console()
    console.print(f"Finalizing {title}  (eval={'on' if with_eval else 'off'}, judge={'on' if with_judge else 'off'}, caps={rank_caps or 'none'})")
    result = finalize_title(
        title=title,
        moments_path=moments,
        output_dir=REPO_ROOT / "data" / "outputs",
        generator_outputs=[Path(o) for o in outputs],
        run_eval=with_eval,
        run_judge=with_judge,
        cfg=cfg,
        rank_caps=rank_caps if rank_caps else None,
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
