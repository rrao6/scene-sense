"""End-to-end pipeline orchestration: VLM JSON -> validated client bundle.

Replaces the old subprocess-based `scripts/run_all.py`. Every pipeline runs
in-process so errors bubble up cleanly and there's only one Python startup.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from rich.console import Console
from rich.table import Table

log = logging.getLogger(__name__)
console = Console()


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")


def run(
    *,
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
    repo_root: Path,
) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    from ..realism.config import load_config
    from ..realism.moments import load_moments

    cfg = load_config(repo_root / ".env")
    cfg.cache_dir = repo_root / cfg.cache_dir
    cfg.outputs_dir = repo_root / cfg.outputs_dir
    cfg.source_bank_dir = repo_root / cfg.source_bank_dir
    cfg.ensure_dirs()

    tm = load_moments(moments_path)
    title = tm.title
    slug = _slug(title)
    out_dir = repo_root / "data" / "outputs"
    console.print(f"[bold cyan]▶ Running full pipeline for:[/bold cyan] {title}")
    console.print(f"  Moments: {moments_path}")
    console.print(f"  Domains: {domains or '(auto-detect)'}")
    console.print()

    results: dict[str, bool] = {}

    # ---- tier0 ----
    if not skip_tier0:
        console.print("[bold]→ tier0[/bold]")
        try:
            from ..tier0.extract import extract_all_tier0

            payload = extract_all_tier0(moments_path)
            (out_dir / f"{slug}.tier0.json").write_text(json.dumps(payload, indent=2))
            results["tier0"] = True
        except Exception as exc:  # pragma: no cover — operational visibility
            log.exception("tier0 failed: %s", exc)
            results["tier0"] = False
        _mark(results["tier0"], "tier0")

    # ---- trivia ----
    if not skip_trivia:
        console.print("[bold]→ trivia[/bold]")
        try:
            from ..trivia.pipeline import run_trivia_pipeline

            run_trivia_pipeline(cfg=cfg, moments_path=moments_path, scene_limit=trivia_scenes)
            results["trivia"] = (out_dir / f"{slug}.trivia.json").exists()
        except Exception as exc:  # pragma: no cover
            log.exception("trivia failed: %s", exc)
            results["trivia"] = False
        _mark(results["trivia"], "trivia")

    # ---- hriv2 ----
    if not skip_hriv2:
        console.print("[bold]→ hriv2[/bold]")
        try:
            from ..realism_v2.pipeline import run_hriv2_pipeline

            run_hriv2_pipeline(
                cfg=cfg, moments_path=moments_path,
                scene_limit=hriv2_scenes,
                domain_override=list(domains) if domains else None,
            )
            results["hriv2"] = (out_dir / f"{slug}.hriv2.json").exists()
        except Exception as exc:  # pragma: no cover
            log.exception("hriv2 failed: %s", exc)
            results["hriv2"] = False
        _mark(results["hriv2"], "hriv2")

    # ---- facts ----
    if not skip_facts:
        console.print("[bold]→ facts[/bold]")
        try:
            from ..facts.pipeline import run_facts_pipeline

            run_facts_pipeline(cfg=cfg, moments_path=moments_path, topic_count=fact_topics)
            results["facts"] = (out_dir / f"{slug}.facts.json").exists()
        except Exception as exc:  # pragma: no cover
            log.exception("facts failed: %s", exc)
            results["facts"] = False
        _mark(results["facts"], "facts")

    # ---- cast ----
    if not skip_cast:
        console.print("[bold]→ cast_enriched[/bold]")
        try:
            from ..cast_enrichment.pipeline import run_cast_enrichment

            run_cast_enrichment(cfg=cfg, moments_path=moments_path, max_actors=max_actors)
            results["cast"] = (out_dir / f"{slug}.cast_enriched.json").exists()
        except Exception as exc:  # pragma: no cover
            log.exception("cast_enriched failed: %s", exc)
            results["cast"] = False
        _mark(results["cast"], "cast_enriched")

    # ---- finalize ----
    console.print()
    console.print("[bold]→ finalize[/bold]")
    try:
        from ..eval.finalize import finalize_title

        finalize_outputs: list[Path] = []
        for fn in [f"{slug}.tier0.json", f"{slug}.cast_enriched.json",
                   f"{slug}.trivia.json", f"{slug}.hriv2.json",
                   f"{slug}.facts.json"]:
            p = out_dir / fn
            if p.exists():
                finalize_outputs.append(p)
        finalize_title(
            title=title, moments_path=moments_path,
            output_dir=out_dir, generator_outputs=finalize_outputs,
            run_eval=with_eval, run_judge=False, cfg=None,
        )
        results["finalize"] = (out_dir / f"{slug}.ui.json").exists()
    except Exception as exc:  # pragma: no cover
        log.exception("finalize failed: %s", exc)
        results["finalize"] = False
    _mark(results["finalize"], "finalize")

    # ---- summary ----
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


def _mark(ok: bool, label: str) -> None:
    icon = "[green]✓[/green]" if ok else "[red]✗[/red]"
    console.print(f"  {icon} {label}")
