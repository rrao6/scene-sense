"""In-process eval harness. Reuses logic from scripts/eval_outputs.py but callable from code."""
from __future__ import annotations

import logging
import re
from typing import Any

from ..realism.source_bank import (
    _best_substring_ratio,
    _fetch_url_text,
    _fetch_youtube_transcript,
)

log = logging.getLogger(__name__)


def _title_tokens(title: str) -> list[str]:
    return [t for t in re.split(r"\W+", (title or "").lower()) if len(t) >= 4]


def _check_title_grounding(title: str, body: str) -> tuple[bool, int, int]:
    tokens = _title_tokens(title)
    if not tokens:
        return True, 0, 0
    hits = sum(1 for t in tokens if t in body.lower())
    return hits >= max(1, len(tokens) // 2), hits, len(tokens)


def _fetch(url: str) -> tuple[bool, str, str]:
    if not url:
        return False, "", "no_url"
    if "youtube.com" in url or "youtu.be" in url:
        ok, text_or_err, _ = _fetch_youtube_transcript(url)
        if ok:
            return True, text_or_err, "youtube_transcript"
        ok2, body_or_err = _fetch_url_text(url, timeout_s=15)
        if ok2:
            return True, body_or_err, "youtube_page_fallback"
        return False, "", body_or_err
    ok, body_or_err = _fetch_url_text(url, timeout_s=15)
    return ok, (body_or_err if ok else ""), (body_or_err if not ok else "ok")


def deterministic_eval(title: str, p: dict) -> dict[str, Any]:
    """Re-fetch the cited source(s) and check the prompt's claims against live web text.

    Returns a report dict compatible with score_accuracy(eval_report=...).
    """
    prim = p.get("primitive")
    if prim == "how_real_is_it":
        return _eval_realism(title, p)
    if prim == "trivia":
        return _eval_trivia(title, p)
    if prim in ("scene_iq", "cast"):
        # Tier-0 songs/cast carry OG verification; tier-0 wiki re-verifies against live wiki
        t0 = (p.get("tier0_meta") or {}).get("source_field")
        if t0 == "wikipedia_trivia":
            return _eval_tier0_wiki(title, p)
        return {"pass": True, "notes": ["tier0_og_verified"]}
    return {"pass": True, "notes": ["unknown_primitive_no_eval"]}


def _eval_realism(title: str, p: dict) -> dict[str, Any]:
    rm = p.get("realism") or {}
    grounding = rm.get("grounding_type", "")
    if grounding == "generalized_source_supported":
        gs = rm.get("generalized_sources") or []
        if not gs:
            return {"pass": False, "notes": ["no_generalized_source"]}
        # Try the primary URL and any statute-library fallbacks (e.g. uscourts.gov PDF for Cornell LII FRE pages).
        from ..realism.statutes import STATUTES
        fallback_by_citation: dict[str, list[str]] = {
            s.citation: (s.fallback_urls or []) for s in STATUTES
        }
        for g in gs:
            url = g.get("url", "")
            if url:
                ok, _body, _note = _fetch(url)
                if ok:
                    return {"pass": True, "notes": ["statute_url_resolved"]}
            # try alternates for this citation
            for alt in fallback_by_citation.get(g.get("citation", ""), []):
                ok_alt, _b, _n = _fetch(alt)
                if ok_alt:
                    return {"pass": True, "notes": [f"statute_fallback_resolved:{alt[:50]}"]}
        return {"pass": False, "notes": ["all_generalized_urls_failed"]}

    used_quotes = [q for q in (rm.get("direct_quotes") or []) if q.get("used_in_drawer")]
    if not used_quotes:
        used_quotes = (rm.get("direct_quotes") or [])[:1]
    if not used_quotes:
        return {"pass": False, "notes": ["no_quote_urls"]}

    verified = 0
    fetched_any = False
    notes: list[str] = []
    for q in used_quotes:
        url = q.get("source_url", "")
        if not url:
            continue
        ok, body, note = _fetch(url)
        if not ok:
            notes.append(f"fetch_failed:{note[:40]}")
            continue
        fetched_any = True
        tg_ok, _hits, _total = _check_title_grounding(title, body)
        if not tg_ok:
            notes.append("title_not_grounded")
            continue
        ratio = _best_substring_ratio(q.get("text", ""), body)
        if ratio >= 0.85:
            verified += 1
        elif "youtube" in url and ratio >= 0.4:
            verified += 1
    passed = fetched_any and verified >= 1
    if verified < len(used_quotes):
        notes.append("some_quotes_not_in_body")
    return {"pass": passed, "notes": notes}


def _eval_trivia(title: str, p: dict) -> dict[str, Any]:
    url = (p.get("source_citations") or [{}])[0].get("url", "")
    tm = p.get("trivia_meta") or {}
    snippet = (tm.get("fact_snippet") or "").strip()
    answer = next((o["label"] for o in (p.get("options") or []) if o.get("correct")), "")
    ok, body, note = _fetch(url)
    if not ok:
        return {"pass": False, "notes": [f"fetch_failed:{note[:40]}"]}
    tg_ok, _hits, _total = _check_title_grounding(title, body)
    snip_r = _best_substring_ratio(snippet, body) if snippet else 0.0
    ans_r = _best_substring_ratio(answer, snippet) if snippet else 0.0
    passed = tg_ok and snip_r >= 0.80 and ans_r >= 0.80
    notes: list[str] = []
    if not tg_ok:
        notes.append("title_not_grounded")
    if snip_r < 0.80:
        notes.append(f"snippet_not_in_body({snip_r:.2f})")
    if ans_r < 0.80:
        notes.append(f"answer_not_in_snippet({ans_r:.2f})")
    return {"pass": passed, "notes": notes}


def _eval_tier0_wiki(title: str, p: dict) -> dict[str, Any]:
    url = (p.get("source_citations") or [{}])[0].get("url", "")
    body_text = p.get("drawer") or p.get("body") or ""
    ok, body, note = _fetch(url)
    if not ok:
        return {"pass": False, "notes": [f"fetch_failed:{note[:40]}"]}
    ratio = _best_substring_ratio(body_text, body)
    if ratio < 0.80:
        return {"pass": False, "notes": [f"fact_not_in_wiki_body({ratio:.2f})"]}
    return {"pass": True, "notes": []}
