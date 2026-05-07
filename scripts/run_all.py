#!/usr/bin/env python3
"""Single entry point: VLM JSON in, client UI bundle out.

Runs: tier0 -> (trivia + hriv2 + facts + cast_enrichment in parallel) -> finalize.

Example:
    python scripts/run_all.py data/samples/Gladiator.json \\
        --domain historical --trivia-scenes 10 --hriv2-scenes 15 --topics 8

Outputs written to data/outputs/:
    <title>.tier0.json         — no-API wiki + song + detected-cast facts
    <title>.trivia.json         — MCQ cards with cross-source verification
    <title>.hriv2.json          — myth-busting realism cards (historical / legal / etc.)
    <title>.facts.json          — editorial BTS cards
    <title>.cast_enriched.json  — actor career facts
    <title>.final.json          — full-fidelity consolidated record
    <title>.review.json         — detailed per-card scores
    <title>.cards.md            — human-readable HITL review
    <title>.cards.json          — slim cards JSON
    <title>.ui.json             — CLIENT CONTRACT: actorFact/sceneFact/actorTrivia/sceneTrivia
"""
from __future__ import annotations

import logging
import subprocess
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
from scene_sense.realism.moments import load_moments  # noqa: E402


def _slug(text: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")


@click.command()
@click.argument("moments_path", type=click.Path(exists=True, dir_okay=False))
@click.option("--domain", "domains", multiple=True, default=None,
              help="Override domain(s) for hriv2 (legal, historical, medical, etc.)")
@click.option("--trivia-scenes", type=int, default=8)
@click.option("--hriv2-scenes", type=int, default=10)
@click.option("--topics", "fact_topics", type=int, default=8)
@click.option("--max-actors", type=int, default=10)
@click.option("--skip-tier0", is_flag=True, default=False)
@click.option("--skip-trivia", is_flag=True, default=False)
@click.option("--skip-hriv2", is_flag=True, default=False)
@click.option("--skip-facts", is_flag=True, default=False)
@click.option("--skip-cast", is_flag=True, default=False)
@click.option("--with-eval/--no-eval", default=False,
              help="Run deterministic re-fetch eval during finalize")
def main(
    moments_path: str,
    domains: tuple[str, ...],
    trivia_scenes: int,
    hriv2_scenes: int,
    fact_topics: int,
    max_actors: int,
    skip_tier0: bool,
    skip_trivia: bool,
    skip_hriv2: bool,
    skip_facts: bool,
    skip_cast: bool,
    with_eval: bool,
) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    console = Console()

    cfg = load_config(REPO_ROOT / ".env")
    cfg.cache_dir = REPO_ROOT / cfg.cache_dir
    cfg.outputs_dir = REPO_ROOT / cfg.outputs_dir
    cfg.source_bank_dir = REPO_ROOT / cfg.source_bank_dir
    cfg.ensure_dirs()

    tm = load_moments(moments_path)
    title = tm.title
    slug = _slug(title)
    out_dir = REPO_ROOT / "data" / "outputs"
    console.print(f"[bold cyan]▶ Running full pipeline for:[/bold cyan] {title}")
    console.print(f"  Moments: {moments_path}")
    console.print(f"  Domains: {domains or '(auto-detect)'}")
    console.print()

    # ---- Stage 1: per-primitive generation ----
    stages: list[tuple[str, list[str], str]] = []  # (name, cmd, output_file_tail)

    if not skip_tier0:
        stages.append((
            "tier0",
            ["python", "scripts/generate_tier0.py", moments_path],
            f"{slug}.tier0.json",
        ))
    if not skip_trivia:
        stages.append((
            "trivia",
            ["python", "scripts/generate_trivia.py", moments_path, "--limit", str(trivia_scenes)],
            f"{slug}.trivia.json",
        ))
    if not skip_hriv2:
        domain_args: list[str] = []
        for d in (domains or ()):
            domain_args.extend(["--domain", d])
        stages.append((
            "hriv2",
            ["python", "scripts/generate_hriv2.py", moments_path, "--limit", str(hriv2_scenes), *domain_args],
            f"{slug}.hriv2.json",
        ))
    if not skip_facts:
        stages.append((
            "facts",
            ["python", "scripts/generate_facts.py", moments_path, "--topics", str(fact_topics)],
            f"{slug}.facts.json",
        ))
    if not skip_cast:
        stages.append((
            "cast_enriched",
            ["python", "scripts/generate_cast_enriched.py", moments_path, "--max-actors", str(max_actors)],
            f"{slug}.cast_enriched.json",
        ))

    results: dict[str, bool] = {}
    for stage_name, cmd, out_file in stages:
        console.print(f"[bold]→ {stage_name}[/bold]")
        rc = subprocess.call(cmd, cwd=str(REPO_ROOT))
        exists = (out_dir / out_file).exists()
        results[stage_name] = rc == 0 and exists
        console.print(
            f"  {'[green]✓[/green]' if results[stage_name] else '[red]✗[/red]'} "
            f"{stage_name} (rc={rc}, output={'found' if exists else 'missing'})"
        )

    # ---- Stage 2: finalize ----
    console.print()
    console.print("[bold]→ finalize[/bold]")
    finalize_outputs: list[str] = []
    # Prefer tier0 + cast_enriched (cast_enriched OVERRIDES tier0's placeholder cast)
    # Then trivia, hriv2, facts.
    for out_file in [
        f"{slug}.tier0.json",
        f"{slug}.cast_enriched.json",
        f"{slug}.trivia.json",
        f"{slug}.hriv2.json",
        f"{slug}.facts.json",
    ]:
        p = out_dir / out_file
        if p.exists():
            finalize_outputs.extend(["--outputs", str(p)])

    cmd = [
        "python", "scripts/finalize.py",
        "--title", title,
        "--moments", moments_path,
        *finalize_outputs,
        "--with-eval" if with_eval else "--no-eval",
    ]
    rc = subprocess.call(cmd, cwd=str(REPO_ROOT))
    console.print(f"  {'[green]✓[/green]' if rc == 0 else '[red]✗[/red]'} finalize (rc={rc})")

    # ---- Summary ----
    console.print()
    console.print("[bold cyan]Files produced:[/bold cyan]")
    t = Table(show_header=True)
    t.add_column("File")
    t.add_column("Purpose")
    t.add_column("Status")
    expected = [
        (f"{slug}.tier0.json", "Tier-0 (wiki + songs + cast)"),
        (f"{slug}.cast_enriched.json", "Actor career facts"),
        (f"{slug}.trivia.json", "MCQ trivia cards"),
        (f"{slug}.hriv2.json", "Myth-busting realism cards"),
        (f"{slug}.facts.json", "Editorial BTS cards"),
        (f"{slug}.final.json", "Full audit record"),
        (f"{slug}.review.json", "Detailed per-card scores"),
        (f"{slug}.cards.md", "Human HITL review"),
        (f"{slug}.cards.json", "Slim cards JSON"),
        (f"{slug}.ui.json", "CLIENT CONTRACT UI bundle"),
    ]
    for fn, purpose in expected:
        exists = (out_dir / fn).exists()
        t.add_row(fn, purpose, "[green]✓[/green]" if exists else "[red]missing[/red]")
    console.print(t)


if __name__ == "__main__":
    main()
