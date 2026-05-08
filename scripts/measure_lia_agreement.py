#!/usr/bin/env python3
"""Measure pipeline agreement with Lia's LB gold set.

Usage:
    python scripts/measure_lia_agreement.py data/outputs/legally_blonde.trivia.json

Matches gold-set cards to pipeline cards by scene + fuzzy headline match, then reports:
  - total agreement rate (approve/reject/approve_with_edit all must match)
  - confusion matrix (gold x pipeline)
  - false positives: pipeline approved what Lia rejected
  - false negatives: pipeline rejected what Lia approved
  - coverage: how many gold cards have a pipeline match
  - top reject reasons from gold (to tell you where your gates should focus)
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

REPO_ROOT = Path(__file__).resolve().parent.parent
GOLD = REPO_ROOT / "data" / "eval" / "lia_gold_lb.json"


def _norm(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio()


def _pipeline_verdict(p: dict) -> str:
    """Return approve | reject | approve_with_edit from generator output."""
    tm = p.get("trivia_meta") or {}
    v = tm.get("validator") or {}
    passed = v.get("passed")
    if passed is True:
        return "approve"
    if passed is False:
        return "reject"
    # finalizer verdict if present
    ev = p.get("_eval") or {}
    return ev.get("verdict", "?")


@click.command()
@click.argument("pipeline_output", type=click.Path(exists=True, dir_okay=False))
@click.option("--gold", type=click.Path(exists=True), default=str(GOLD))
@click.option("--min-match", type=float, default=0.55,
              help="Minimum fuzzy-match ratio (headline) to count a gold<->pipeline pair.")
def main(pipeline_output: str, gold: str, min_match: float) -> None:
    console = Console()
    gold_data = json.loads(Path(gold).read_text())
    pipe_data = json.loads(Path(pipeline_output).read_text())

    gold_entries = gold_data["verdicts"]
    pipe_prompts = pipe_data.get("prompts") or pipe_data.get("cards") or []

    # Index pipeline prompts by scene
    by_scene: dict[int, list[dict]] = defaultdict(list)
    for p in pipe_prompts:
        idx = p.get("scene_index") or p.get("sceneCuepoint", {}).get("sceneIndex")
        if idx is not None:
            by_scene[idx].append(p)

    matches = []
    unmatched_gold = []
    for g in gold_entries:
        scene = g["scene"]
        g_head = g["headline"]
        candidates = by_scene.get(scene, [])
        best = None
        best_r = 0.0
        for p in candidates:
            ph = p.get("headline") or p.get("factHeader") or p.get("triviaText") or ""
            r = _ratio(g_head, ph)
            if r > best_r:
                best_r = r
                best = p
        if best and best_r >= min_match:
            matches.append((g, best, best_r))
        else:
            unmatched_gold.append(g)

    # Tally
    confusion = Counter()
    correct = 0
    false_pos = []  # pipeline approved, Lia rejected
    false_neg = []  # pipeline rejected, Lia approved

    for g, p, r in matches:
        gv = g["verdict"]
        pv = _pipeline_verdict(p)
        # Collapse approve_with_edit to approve for false-pos/neg counting,
        # but track exact match separately.
        gv_bucket = "approve" if gv in ("approve", "approve_with_edit") else "reject"
        pv_bucket = "approve" if pv in ("approve", "approve_with_edit") else "reject"
        exact = (gv == pv)
        if exact:
            correct += 1
        confusion[(gv, pv)] += 1
        if gv_bucket == "reject" and pv_bucket == "approve":
            false_pos.append((g, p, r))
        elif gv_bucket == "approve" and pv_bucket == "reject":
            false_neg.append((g, p, r))

    # Print
    total_matched = len(matches)
    console.print(f"\n[bold cyan]Agreement with Lia on {pipeline_output}[/bold cyan]")
    console.print(f"  Gold entries: {len(gold_entries)}")
    console.print(f"  Pipeline prompts: {len(pipe_prompts)}")
    console.print(f"  Matched (fuzzy ratio ≥ {min_match}): {total_matched}")
    console.print(f"  Unmatched gold: {len(unmatched_gold)}")
    if total_matched:
        console.print(f"\n[bold]Exact agreement:[/bold] {correct}/{total_matched} "
                      f"= [bold magenta]{100*correct/total_matched:.1f}%[/bold magenta]")
        bucket_correct = sum(1 for g, p, _ in matches
                             if (g["verdict"] in ("approve","approve_with_edit")) ==
                                (_pipeline_verdict(p) in ("approve","approve_with_edit")))
        console.print(f"[bold]Bucket agreement (approve* vs reject):[/bold] "
                      f"{bucket_correct}/{total_matched} = {100*bucket_correct/total_matched:.1f}%")

    # Confusion table
    t = Table(title="Confusion (gold → pipeline)", show_header=True)
    t.add_column("Gold", style="cyan")
    t.add_column("Pipeline", style="magenta")
    t.add_column("Count", style="yellow")
    for (gv, pv), c in sorted(confusion.items(), key=lambda x: -x[1]):
        t.add_row(gv, pv, str(c))
    console.print(t)

    # False positives (worst errors — pipeline shipped what Lia would kill)
    if false_pos:
        console.print(f"\n[bold red]False positives ({len(false_pos)})[/bold red] "
                      f"— pipeline approved, Lia rejected:")
        for g, p, r in false_pos[:10]:
            console.print(f"  scene {g['scene']} · '{g['headline']}'")
            console.print(f"    Lia: {g['verdict']} — {', '.join(g['reasons'])}")
            console.print(f"    Pipeline: {_pipeline_verdict(p)}")

    # False negatives (pipeline rejected what Lia approved)
    if false_neg:
        console.print(f"\n[bold yellow]False negatives ({len(false_neg)})[/bold yellow] "
                      f"— pipeline rejected, Lia approved:")
        for g, p, r in false_neg[:10]:
            console.print(f"  scene {g['scene']} · '{g['headline']}'")
            console.print(f"    Lia: {g['verdict']}")
            console.print(f"    Pipeline: {_pipeline_verdict(p)}")

    # Top taxonomy reasons from gold — where your gates should focus
    tax = Counter()
    for g in gold_entries:
        if g["verdict"] == "reject":
            for t_ in g.get("taxonomy", []):
                tax[t_] += 1
    console.print("\n[bold]Lia's reject taxonomy (what gates to build):[/bold]")
    for t_, c in tax.most_common():
        console.print(f"  {c}x  {t_}")


if __name__ == "__main__":
    main()
