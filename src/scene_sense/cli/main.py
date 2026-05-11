"""scene-sense CLI.

Single entry point for every pipeline and for the hand-curated demo bundle.

Subcommands:
  demo         Copy the curated Legally Blonde demo bundle to an output dir. No API keys needed.
  tier0        Deterministic wiki/song/cast extraction from VLM JSON.
  trivia       Scene-anchored MCQ generation (requires GEMINI_API_KEY).
  hriv2        How Real Is It? myth-bust cards (requires GEMINI_API_KEY).
  facts        Editorial BTS fact cards (requires GEMINI_API_KEY).
  cast         Grounded cast-enrichment cards (requires GEMINI_API_KEY).
  finalize     Dedup + score + emit client UI bundle from one-or-more pipeline outputs.
  run-all      Run every pipeline end-to-end for a title.
  validate     Validate a UI bundle JSON against the schema contract (no network).
  version      Print version.
"""
from __future__ import annotations

import json
import logging
import shutil
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from .. import __version__
from ..demo import bundle as demo_bundle


console = Console()


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )


def _repo_root() -> Path:
    """Resolve the repo root when running from a checkout.

    Falls back to the CWD if the installed package is not sitting inside a repo
    (rare — only `scene-sense demo` needs write access outside the package, and
    it uses --out).
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").exists() or (parent / "data" / "samples").exists():
            return parent
    return Path.cwd()


def _load_runtime_cfg():
    """Import + construct the runtime config lazily so subcommands that don't
    need LLM credentials (demo, validate, version) never touch Gemini settings.
    """
    from ..realism.config import load_config  # noqa: WPS433

    root = _repo_root()
    cfg = load_config(root / ".env")
    cfg.cache_dir = root / cfg.cache_dir
    cfg.outputs_dir = root / cfg.outputs_dir
    cfg.source_bank_dir = root / cfg.source_bank_dir
    cfg.ensure_dirs()
    return cfg


@click.group(help=__doc__)
@click.version_option(version=__version__, prog_name="scene-sense")
def cli() -> None:
    pass


# ------------------------------------------------------------------ demo


@cli.command("demo", help="Copy the hand-curated Legally Blonde demo bundle to an output dir.")
@click.option(
    "--out", "out_dir",
    type=click.Path(file_okay=False),
    default="data/outputs",
    show_default=True,
    help="Directory to copy demo files into.",
)
@click.option("--title", default="legally_blonde", show_default=True, help="Demo title slug (only 'legally_blonde' is packaged today).")
def cmd_demo(out_dir: str, title: str) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written = demo_bundle.copy_to(title=title, dest=out)

    t = Table(title=f"Demo bundle: {title}", show_header=True)
    t.add_column("File", style="cyan")
    t.add_column("Size", style="magenta", justify="right")
    t.add_column("Cards", style="green", justify="right")
    for path, size, cards in written:
        t.add_row(str(path), f"{size:,} B", str(cards) if cards is not None else "-")
    console.print(t)
    console.print(f"[green]Wrote {len(written)} file(s) to {out}[/green]")


# ------------------------------------------------------------------ validate


@cli.command("validate", help="Validate a UI bundle JSON against the schema contract.")
@click.argument("bundle_path", type=click.Path(exists=True, dir_okay=False))
def cmd_validate(bundle_path: str) -> None:
    from ..ui_schema.contract import validate_bundle  # noqa: WPS433

    data = json.loads(Path(bundle_path).read_text())
    report = validate_bundle(data)
    t = Table(title=f"Validate: {bundle_path}", show_header=True)
    t.add_column("Check", style="cyan")
    t.add_column("Result", style="magenta")
    for check, ok, note in report.checks:
        color = "green" if ok else "red"
        t.add_row(check, f"[{color}]{'PASS' if ok else 'FAIL'}[/{color}] {note or ''}")
    console.print(t)
    if not report.ok:
        sys.exit(1)


# ------------------------------------------------------------------ version


@cli.command("version")
def cmd_version() -> None:
    click.echo(__version__)


# ------------------------------------------------------------------ tier0


@cli.command("tier0", help="Deterministic wiki/song/cast extraction from VLM JSON. No API calls.")
@click.argument("moments_path", type=click.Path(exists=True, dir_okay=False))
def cmd_tier0(moments_path: str) -> None:
    _setup_logging(False)
    from ..tier0.extract import extract_all_tier0  # noqa: WPS433

    result = extract_all_tier0(moments_path)
    out_dir = _repo_root() / "data" / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = _slug(result["title"])
    out_path = out_dir / f"{slug}.tier0.json"
    out_path.write_text(json.dumps(result, indent=2))

    t = Table(title=f"Tier-0 prompts: {result['title']}", show_header=True)
    t.add_column("Source", style="cyan")
    t.add_column("Count", style="magenta")
    for k, v in result["counts"].items():
        t.add_row(k, str(v))
    t.add_row("Output", str(out_path))
    console.print(t)


# ------------------------------------------------------------------ trivia


@cli.command("trivia", help="Scene-anchored MCQ trivia generation. Requires GEMINI_API_KEY.")
@click.argument("moments_path", type=click.Path(exists=True, dir_okay=False))
@click.option("--limit", type=int, default=None)
@click.option("--topics", "topic_count", type=int, default=6)
@click.option("--fame-min", type=int, default=3)
@click.option("--verbose", is_flag=True, default=False)
def cmd_trivia(moments_path: str, limit: int | None, topic_count: int, fame_min: int, verbose: bool) -> None:
    _setup_logging(verbose)
    from ..trivia.pipeline import run_trivia_pipeline  # noqa: WPS433

    cfg = _load_runtime_cfg()
    summary = run_trivia_pipeline(
        cfg=cfg, moments_path=moments_path,
        scene_limit=limit, topic_count=topic_count, fame_min_score=fame_min,
    )
    _print_summary("Trivia", summary)


# ------------------------------------------------------------------ hriv2


@cli.command("hriv2", help="How Real Is It? myth-bust cards. Requires GEMINI_API_KEY.")
@click.argument("moments_path", type=click.Path(exists=True, dir_okay=False))
@click.option("--limit", type=int, default=None)
@click.option("--domain", "domains", multiple=True, default=None)
@click.option("--verbose", is_flag=True, default=False)
def cmd_hriv2(moments_path: str, limit: int | None, domains: tuple[str, ...], verbose: bool) -> None:
    _setup_logging(verbose)
    from ..realism_v2.pipeline import run_hriv2_pipeline  # noqa: WPS433

    cfg = _load_runtime_cfg()
    summary = run_hriv2_pipeline(
        cfg=cfg, moments_path=moments_path,
        scene_limit=limit, domain_override=list(domains) if domains else None,
    )
    _print_summary("How Real Is It v2", summary)


# ------------------------------------------------------------------ facts


@cli.command("facts", help="Editorial BTS facts. Requires GEMINI_API_KEY.")
@click.argument("moments_path", type=click.Path(exists=True, dir_okay=False))
@click.option("--topics", "topic_count", type=int, default=8)
@click.option("--verbose", is_flag=True, default=False)
def cmd_facts(moments_path: str, topic_count: int, verbose: bool) -> None:
    _setup_logging(verbose)
    from ..facts.pipeline import run_facts_pipeline  # noqa: WPS433

    cfg = _load_runtime_cfg()
    summary = run_facts_pipeline(cfg=cfg, moments_path=moments_path, topic_count=topic_count)
    _print_summary("Facts (BTS)", summary)


# ------------------------------------------------------------------ cast


@cli.command("cast", help="Grounded cast enrichment. Requires GEMINI_API_KEY.")
@click.argument("moments_path", type=click.Path(exists=True, dir_okay=False))
@click.option("--max-actors", type=int, default=10)
@click.option("--verbose", is_flag=True, default=False)
def cmd_cast(moments_path: str, max_actors: int, verbose: bool) -> None:
    _setup_logging(verbose)
    from ..cast_enrichment.pipeline import run_cast_enrichment  # noqa: WPS433

    cfg = _load_runtime_cfg()
    summary = run_cast_enrichment(cfg=cfg, moments_path=moments_path, max_actors=max_actors)
    _print_summary("Cast enrichment", summary)


# ------------------------------------------------------------------ finalize


@cli.command("finalize", help="Dedup + score pipeline outputs into a client-ready UI bundle.")
@click.option("--title", required=True)
@click.option("--moments", required=True, type=click.Path(exists=True, dir_okay=False))
@click.option("--outputs", "outputs", multiple=True, required=True, type=click.Path(dir_okay=False))
@click.option("--with-eval/--no-eval", default=True)
@click.option("--with-judge/--no-judge", default=False)
def cmd_finalize(title: str, moments: str, outputs: tuple[str, ...],
                 with_eval: bool, with_judge: bool) -> None:
    from ..eval.finalize import finalize_title  # noqa: WPS433

    cfg = _load_runtime_cfg() if with_judge else None
    result = finalize_title(
        title=title, moments_path=moments,
        output_dir=_repo_root() / "data" / "outputs",
        generator_outputs=[Path(o) for o in outputs],
        run_eval=with_eval, run_judge=with_judge, cfg=cfg,
    )
    t = Table(title=f"Finalize: {result.title}", show_header=True)
    t.add_column("Metric", style="cyan")
    t.add_column("Value", style="magenta")
    t.add_row("Total prompts (after dedup)", str(result.total_prompts))
    t.add_row("Dedup removed", str(result.dedup_removed))
    t.add_row("Per primitive", ", ".join(f"{k}:{v}" for k, v in result.per_primitive.items()))
    t.add_row("Per verdict", ", ".join(f"{k}:{v}" for k, v in result.per_verdict.items()))
    t.add_row("Overall avg score", str(result.overall_avg))
    console.print(t)


# ------------------------------------------------------------------ run-all


@cli.command("run-all", help="Run every pipeline end-to-end for a single VLM JSON.")
@click.argument("moments_path", type=click.Path(exists=True, dir_okay=False))
@click.option("--domain", "domains", multiple=True, default=None)
@click.option("--trivia-scenes", type=int, default=8)
@click.option("--hriv2-scenes", type=int, default=10)
@click.option("--topics", "fact_topics", type=int, default=8)
@click.option("--max-actors", type=int, default=10)
@click.option("--skip-tier0", is_flag=True, default=False)
@click.option("--skip-trivia", is_flag=True, default=False)
@click.option("--skip-hriv2", is_flag=True, default=False)
@click.option("--skip-facts", is_flag=True, default=False)
@click.option("--skip-cast", is_flag=True, default=False)
@click.option("--with-eval/--no-eval", default=False)
def cmd_run_all(moments_path: str, domains: tuple[str, ...],
                trivia_scenes: int, hriv2_scenes: int, fact_topics: int, max_actors: int,
                skip_tier0: bool, skip_trivia: bool, skip_hriv2: bool,
                skip_facts: bool, skip_cast: bool, with_eval: bool) -> None:
    """Thin wrapper around scripts/run_all.py for backwards-compat."""
    from . import run_all_impl  # noqa: WPS433

    run_all_impl.run(
        moments_path=moments_path,
        domains=domains,
        trivia_scenes=trivia_scenes,
        hriv2_scenes=hriv2_scenes,
        fact_topics=fact_topics,
        max_actors=max_actors,
        skip_tier0=skip_tier0,
        skip_trivia=skip_trivia,
        skip_hriv2=skip_hriv2,
        skip_facts=skip_facts,
        skip_cast=skip_cast,
        with_eval=with_eval,
        repo_root=_repo_root(),
    )


# ------------------------------------------------------------------ helpers


def _slug(text: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")


def _print_summary(label: str, summary) -> None:
    t = Table(title=label, show_header=True)
    t.add_column("Metric", style="cyan")
    t.add_column("Value", style="magenta")
    for field_name in getattr(summary, "__dataclass_fields__", {}):
        t.add_row(field_name, str(getattr(summary, field_name)))
    console.print(t)


if __name__ == "__main__":
    cli()
