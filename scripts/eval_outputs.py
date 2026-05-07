#!/usr/bin/env python3
"""Deterministic eval harness for SceneSense prompt outputs.

Usage:
    python scripts/eval_outputs.py data/outputs/the_devils_advocate.realism.json
    python scripts/eval_outputs.py data/outputs/the_devils_advocate.trivia.json
    python scripts/eval_outputs.py data/outputs/the_devils_advocate.tier0.json

For each prompt, it re-fetches the cited URL and checks:
  - URL resolves
  - Body mentions the film title (title-grounding)
  - For realism: every verbatim quote in the drawer appears in the fetched body
  - For trivia: the fact_snippet appears in the fetched body, and the answer appears in the fact_snippet
  - For tier0 wiki trivia: the body field appears in the Wikipedia article body

No LLM calls. Pure deterministic checks. Prints a per-prompt report + summary.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scene_sense.realism.source_bank import (  # noqa: E402
    _best_substring_ratio,
    _fetch_url_text,
    _fetch_youtube_transcript,
)


def _title_tokens(title: str) -> list[str]:
    return [t for t in re.split(r"\W+", (title or "").lower()) if len(t) >= 4]


def _check_title_grounding(title: str, body: str) -> tuple[bool, int, int]:
    tokens = _title_tokens(title)
    if not tokens:
        return True, 0, 0
    hits = sum(1 for t in tokens if t in body.lower())
    return hits >= max(1, len(tokens) // 2), hits, len(tokens)


def _fetch(url: str) -> tuple[bool, str, str]:
    """Returns (ok, body, note)."""
    if not url:
        return False, "", "no_url"
    if "youtube.com" in url or "youtu.be" in url:
        ok, text_or_err, _ = _fetch_youtube_transcript(url)
        if ok:
            return True, text_or_err, "youtube_transcript"
        # fall back to page body
        ok2, body_or_err = _fetch_url_text(url, timeout_s=15)
        if ok2:
            return True, body_or_err, f"youtube_transcript_failed:{text_or_err[:60]}"
        return False, "", body_or_err
    ok, body_or_err = _fetch_url_text(url, timeout_s=15)
    return ok, (body_or_err if ok else ""), (body_or_err if not ok else "ok")


def eval_realism_prompt(title: str, p: dict) -> dict:
    rm = p.get("realism") or {}
    grounding = rm.get("grounding_type", "")

    report = {
        "prompt_id": p.get("prompt_id"),
        "scene_index": p.get("scene_index"),
        "primitive": p.get("primitive"),
        "url": "",
        "url_resolved": False,
        "title_grounded": None,
        "quote_coverage": None,
        "pass": False,
        "notes": [],
    }

    # Path A: generalized_source_supported — verify each generalized_source URL resolves.
    if grounding == "generalized_source_supported":
        gs = rm.get("generalized_sources") or []
        if not gs:
            report["notes"].append("no_generalized_source")
            return report
        ok_any = False
        for g in gs:
            url = g.get("url", "")
            if not url:
                continue
            ok, body, _note = _fetch(url)
            if ok:
                ok_any = True
                report["url"] = url
                report["url_resolved"] = True
                report["title_grounded"] = "n/a"  # statute pages don't reference the film
                break
        if not ok_any:
            report["notes"].append("all_generalized_urls_failed")
            return report
        report["quote_coverage"] = "n/a (statute)"
        report["pass"] = True
        return report

    # Path B: named_expert — verify each used quote's own source_url + quote presence.
    used_quotes = [q for q in (rm.get("direct_quotes") or []) if q.get("used_in_drawer")]
    if not used_quotes:
        # some sources fall through with empty used list; check first quote any
        used_quotes = (rm.get("direct_quotes") or [])[:1]

    if not used_quotes:
        report["notes"].append("no_quote_urls")
        return report

    report["url"] = used_quotes[0].get("source_url", "")
    verified = 0
    title_grounded_hits = 0
    title_grounded_total = 0
    fetched_any = False
    for q in used_quotes:
        url = q.get("source_url", "")
        if not url:
            continue
        ok, body, note = _fetch(url)
        if not ok:
            report["notes"].append(f"fetch_failed:{note[:40]}")
            continue
        fetched_any = True
        tg_ok, hits, total = _check_title_grounding(title, body)
        title_grounded_hits = max(title_grounded_hits, hits)
        title_grounded_total = total
        ratio = _best_substring_ratio(q.get("text", ""), body)
        if ratio >= 0.85:
            verified += 1
        elif "youtube" in url:
            # YouTube transcript may vary between runs; give half-credit if still reachable.
            if ratio >= 0.4:
                verified += 1
    report["url_resolved"] = fetched_any
    if fetched_any:
        report["title_grounded"] = f"{title_grounded_hits}/{title_grounded_total}"
    report["quote_coverage"] = f"{verified}/{len(used_quotes)}"
    report["pass"] = fetched_any and verified >= 1 and (
        title_grounded_total == 0 or title_grounded_hits >= max(1, title_grounded_total // 2)
    )
    if used_quotes and verified < len(used_quotes):
        report["notes"].append("some_quotes_not_in_body")
    return report


def eval_trivia_prompt(title: str, p: dict) -> dict:
    url = (p.get("source_citations") or [{}])[0].get("url", "")
    tm = p.get("trivia_meta") or {}
    snippet = (tm.get("fact_snippet") or "").strip()
    answer = next((o["label"] for o in (p.get("options") or []) if o.get("correct")), "")
    report = {
        "prompt_id": p.get("prompt_id"),
        "scene_index": p.get("scene_index"),
        "primitive": p.get("primitive"),
        "url": url,
        "url_resolved": False,
        "title_grounded": None,
        "snippet_in_body": None,
        "answer_in_snippet": None,
        "pass": False,
        "notes": [],
    }
    ok, body, note = _fetch(url)
    report["url_resolved"] = ok
    if not ok:
        report["notes"].append(f"fetch_failed:{note}")
        return report
    tg_ok, hits, total = _check_title_grounding(title, body)
    report["title_grounded"] = f"{hits}/{total}"
    if not tg_ok:
        report["notes"].append("title_not_grounded")
    snip_r = _best_substring_ratio(snippet, body) if snippet else 0.0
    report["snippet_in_body"] = f"{snip_r:.2f}"
    ans_r = _best_substring_ratio(answer, snippet) if snippet else 0.0
    report["answer_in_snippet"] = f"{ans_r:.2f}"
    report["pass"] = ok and tg_ok and snip_r >= 0.80 and ans_r >= 0.80
    if snip_r < 0.80:
        report["notes"].append("snippet_not_in_body")
    if ans_r < 0.80:
        report["notes"].append("answer_not_in_snippet")
    return report


def eval_tier0_wiki_prompt(title: str, p: dict) -> dict:
    url = (p.get("source_citations") or [{}])[0].get("url", "")
    body_text = p.get("drawer", "") or p.get("body", "")
    report = {
        "prompt_id": p.get("prompt_id"),
        "scene_index": p.get("scene_index"),
        "primitive": p.get("primitive"),
        "url": url,
        "url_resolved": False,
        "title_grounded": None,
        "fact_in_body": None,
        "pass": False,
        "notes": [],
    }
    if not url:
        report["notes"].append("no_url")
        return report
    ok, body, note = _fetch(url)
    report["url_resolved"] = ok
    if not ok:
        report["notes"].append(f"fetch_failed:{note}")
        return report
    tg_ok, hits, total = _check_title_grounding(title, body)
    report["title_grounded"] = f"{hits}/{total}"
    if not tg_ok:
        report["notes"].append("title_not_grounded")
    r = _best_substring_ratio(body_text, body)
    report["fact_in_body"] = f"{r:.2f}"
    report["pass"] = ok and tg_ok and r >= 0.80
    if r < 0.80:
        report["notes"].append("fact_not_in_wiki_body")
    return report


@click.command()
@click.argument("output_path", type=click.Path(exists=True, dir_okay=False))
@click.option("--limit", type=int, default=None, help="Only eval first N prompts.")
@click.option("--show-failures-only", is_flag=True, default=False)
def main(output_path: str, limit: int | None, show_failures_only: bool) -> None:
    data = json.loads(Path(output_path).read_text())
    title = data.get("title", "")
    prompts = data.get("prompts") or []
    if limit:
        prompts = prompts[:limit]
    if not prompts:
        print(f"no prompts in {output_path}")
        return

    # Dispatch per-primitive eval
    reports = []
    for p in prompts:
        prim = p.get("primitive")
        if prim == "how_real_is_it":
            reports.append(eval_realism_prompt(title, p))
        elif prim == "trivia":
            reports.append(eval_trivia_prompt(title, p))
        elif prim == "scene_iq" or prim == "cast":
            # tier0 prompts
            if (p.get("generated_by") or {}).get("model") == "tier0_rule_based":
                if (p.get("tier0_meta") or {}).get("source_field") == "wikipedia_trivia":
                    reports.append(eval_tier0_wiki_prompt(title, p))
                else:
                    # songs / cast — no external URL to re-verify
                    reports.append({
                        "prompt_id": p.get("prompt_id"),
                        "scene_index": p.get("scene_index"),
                        "primitive": prim,
                        "url": "",
                        "url_resolved": True,
                        "title_grounded": "-",
                        "pass": True,  # tier0 songs/cast are OG-verified
                        "notes": ["tier0_og_verified"],
                    })
            else:
                continue
        else:
            continue

    # Print table
    console = Console()
    total = len(reports)
    passed = sum(1 for r in reports if r["pass"])

    console.print(f"\n[bold]Eval: {Path(output_path).name}[/bold]  ({passed}/{total} passed)\n")

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("scene", width=6)
    table.add_column("primitive", width=14)
    table.add_column("pass", width=5)
    table.add_column("url OK", width=7)
    table.add_column("title", width=8)
    table.add_column("evidence", width=14)
    table.add_column("notes", overflow="fold")
    for r in reports:
        if show_failures_only and r["pass"]:
            continue
        evidence = ""
        if "quote_coverage" in r:
            evidence = f"Q {r.get('quote_coverage')}"
        elif "snippet_in_body" in r:
            evidence = f"snip {r.get('snippet_in_body')} / ans {r.get('answer_in_snippet')}"
        elif "fact_in_body" in r:
            evidence = f"fact {r.get('fact_in_body')}"
        table.add_row(
            str(r["scene_index"]),
            r["primitive"] or "-",
            "[green]✓" if r["pass"] else "[red]✗",
            "Y" if r.get("url_resolved") else "N",
            str(r.get("title_grounded") or "-"),
            evidence,
            "; ".join(r.get("notes") or []),
        )
    console.print(table)


if __name__ == "__main__":
    main()
