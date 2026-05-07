#!/usr/bin/env python3
"""Extract Tier-0 prompts from OG Tubi Moments JSON (no web calls, no LLM).

Usage:
    python scripts/generate_tier0.py data/samples/The_Devils_Advocate.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scene_sense.tier0.extract import extract_all_tier0  # noqa: E402


@click.command()
@click.argument("moments_path", type=click.Path(exists=True, dir_okay=False))
def main(moments_path: str) -> None:
    console = Console()
    result = extract_all_tier0(moments_path)
    out_dir = REPO_ROOT / "data" / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{_slug(result['title'])}.tier0.json"
    out_path.write_text(json.dumps(result, indent=2))

    t = Table(title=f"Tier-0 prompts: {result['title']}", show_header=True)
    t.add_column("Source", style="cyan")
    t.add_column("Count", style="magenta")
    for k, v in result["counts"].items():
        t.add_row(k, str(v))
    t.add_row("Output", str(out_path))
    console.print(t)


def _slug(text: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")


if __name__ == "__main__":
    main()
