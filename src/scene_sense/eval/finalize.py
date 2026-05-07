"""Consolidate all generator outputs for a title into two JSONs:

  <title>.final.json   — full fidelity: all prompts, all scores, all evidence.
  <title>.review.json  — tight HITL review card per prompt; only what a human needs.

Dedup rules (applied across primitives):
  - Same prompt_id -> keep one
  - Same (scene, primitive, semantic-key) -> keep highest-overall-score
  - Tier-0 > Realism > Trivia for same scene when they collide on the same fact (tier0 first)

Scene context (for scoring) is loaded from the OG VLM JSON when available.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ..realism.moments import load_moments
from ..ui_schema.emit import emit_ui_bundle
from .harness import deterministic_eval
from .scorer import score_prompt, PromptScorecard


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")


PRIMITIVE_RANK = {
    "scene_iq": 3,       # tier0 wiki/songs -> highest
    "cast": 2,
    "how_real_is_it": 2,
    "trivia": 1,
}


def _semantic_key(p: dict) -> str:
    """Rough dedup key: primitive + scene + normalized headline+body.

    For cast primitive: key on actor name only — an actor should produce ONE card total,
    regardless of scene, so enriched cards deduplicate against tier0 placeholders.

    For trivia / scene_iq / facts / how_real_is_it: normalize text more aggressively
    (strip common fillers, punctuation, ordering of distractor words) so that
    near-duplicates with different phrasing collide.
    """
    primitive = p.get("primitive", "")
    if primitive == "cast":
        t0 = p.get("tier0_meta") or {}
        actor = (t0.get("celeb_name") or "").strip().lower()
        if not actor:
            m = re.match(r"\s*([A-Z][A-Za-z'\.\-]+(?:\s+[A-Z][A-Za-z'\.\-]+)+)", p.get("body", ""))
            if m:
                actor = m.group(1).strip().lower()
        return f"cast:actor:{actor or p.get('prompt_id','?')}"
    scene = p.get("scene_index", "")
    # Include the correct-answer option text in the dedup key for trivia — cards that
    # ask the same thing differently but have the same correct answer should dedup.
    correct = ""
    for o in (p.get("options") or []):
        if o.get("correct"):
            correct = (o.get("label") or "").lower().strip()
            break
    # Aggressive normalization: lowercase, strip stop-filler words, squash whitespace.
    text = (p.get("headline", "") + " " + p.get("body", "") + " " + correct).lower()
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    STOPFILL = {
        "the","a","an","is","was","were","in","of","that","this","to","for","on","at","by",
        "when","what","who","which","where","how","does","did","do","your","her","his","their",
        "scene","this","film","movie","woods","elle","warner",  # title-specific fillers
        "also","just","really","actually","about","with","from",
    }
    tokens = [t for t in text.split() if t and t not in STOPFILL and len(t) > 1]
    # Sort tokens so different phrasings with same keywords collide.
    normalized = " ".join(sorted(tokens)[:20])
    digest = hashlib.sha256(normalized.encode()).hexdigest()[:12]
    return f"{primitive}:{scene}:{digest}"


def _build_scene_lookup(moments_path: Path | str) -> dict[int, dict]:
    tm = load_moments(moments_path)
    out: dict[int, dict] = {}
    for s in tm.scenes:
        out[s.scene_index] = {
            "scene_index": s.scene_index,
            "start_time": s.start_time,
            "end_time": s.end_time,
            "characters": s.characters,
            "detected_cast": s.detected_cast,
            "key_actions": s.key_actions,
            "key_objects": s.key_objects,
            "dialogue_highlights": s.dialogue_highlights,
            "moderation_severity": s.moderation_severity,
            "summary": s.summary,
        }
    return out


# ---------- review card shape ----------


def _slim_review_card(p: dict, sc: PromptScorecard, scene_ctx: dict | None) -> dict:
    """Minimal card — only what an ops reviewer needs to approve/reject a prompt."""
    options = p.get("options") or []
    answer = next((o["label"] for o in options if o.get("correct")), None)
    distractors = [o["label"] for o in options if not o.get("correct")]
    # collapse source to a domain for readability
    src_url = (p.get("source_citations") or [{}])[0].get("url", "")
    if not src_url and p.get("primitive") == "how_real_is_it":
        rm = p.get("realism") or {}
        dq = rm.get("direct_quotes") or []
        gs = rm.get("generalized_sources") or []
        if dq:
            src_url = dq[0].get("source_url", "")
        elif gs:
            src_url = gs[0].get("url", "")

    card = {
        "scene": p.get("scene_index"),
        "primitive": p.get("primitive"),
        "verdict": sc.verdict(),
        "score": sc.overall(),
        "headline": p.get("headline"),
        "body": p.get("body"),
    }
    if p.get("drawer") and p.get("drawer") != p.get("body"):
        card["drawer"] = p.get("drawer")
    if options:
        card["answer"] = answer
        card["distractors"] = distractors
    if src_url:
        card["source"] = src_url
    if sc.verdict() != "approve":
        card["issues"] = sc.top_issues()
    if p.get("primitive") == "how_real_is_it":
        rm = p.get("realism") or {}
        card["assessment"] = rm.get("assessment")
        experts = [e.get("name") for e in (rm.get("expert_attribution") or []) if e.get("name")]
        if experts:
            card["experts"] = experts
    return card


def _markdown_cards(title: str, cards: list[dict], counts: dict) -> str:
    """Human-scannable markdown, one block per card."""
    out: list[str] = []
    out.append(f"# {title} — SceneSense Review Cards")
    out.append("")
    out.append(f"**{counts['total_prompts']} prompts** · "
               f"✅ {counts['per_verdict'].get('approve', 0)} approve · "
               f"✏️ {counts['per_verdict'].get('needs_edit', 0)} edit · "
               f"❌ {counts['per_verdict'].get('reject', 0)} reject")
    out.append("")
    out.append("---")
    out.append("")
    for c in cards:
        scene = c.get("scene", "?")
        prim = c.get("primitive", "?")
        v = c.get("verdict", "?")
        score = c.get("score", 0.0)
        emoji = {"approve": "✅", "needs_edit": "✏️", "reject": "❌"}.get(v, "·")
        out.append(f"### Scene {scene} · {prim} · {emoji} {v} · {score}")
        out.append("")
        if c.get("headline"):
            out.append(f"**{c['headline']}**")
        if c.get("body"):
            out.append("")
            out.append(c["body"])
        if c.get("drawer"):
            out.append("")
            out.append(f"> {c['drawer']}")
        if c.get("answer") is not None:
            out.append("")
            out.append(f"- ✓ **{c['answer']}**")
            for d in c.get("distractors", []):
                out.append(f"- · {d}")
        if c.get("assessment"):
            out.append("")
            out.append(f"*Realism: {c['assessment']}*" + (
                f" — experts: {', '.join(c['experts'])}" if c.get("experts") else ""
            ))
        if c.get("source"):
            out.append("")
            out.append(f"`source: {c['source']}`")
        if c.get("issues"):
            out.append("")
            out.append(f"⚠️ {' · '.join(c['issues'])}")
        out.append("")
        out.append("---")
        out.append("")
    return "\n".join(out)


def _review_card(p: dict, sc: PromptScorecard, scene_ctx: dict | None) -> dict:
    options = p.get("options") or []
    answer_label = next((o["label"] for o in options if o.get("correct")), None)
    distractors = [o["label"] for o in options if not o.get("correct")]
    source_url = (p.get("source_citations") or [{}])[0].get("url", "")
    if not source_url and p.get("primitive") == "how_real_is_it":
        rm = p.get("realism") or {}
        # fall back to first direct_quote or generalized_source url
        dq = (rm.get("direct_quotes") or [])
        gs = (rm.get("generalized_sources") or [])
        if dq:
            source_url = dq[0].get("source_url", "")
        elif gs:
            source_url = gs[0].get("url", "")

    card = {
        "prompt_id": p.get("prompt_id"),
        "primitive": p.get("primitive"),
        "scene": {
            "index": p.get("scene_index"),
            "time": f"{p.get('scene_start_time','')}–{p.get('scene_end_time','')}",
            "characters": (scene_ctx or {}).get("characters", []),
            "summary": (scene_ctx or {}).get("summary", "")[:180],
        },
        "display": {
            "headline": p.get("headline"),
            "body": p.get("body"),
            "drawer": p.get("drawer"),
        },
        "source_url": source_url,
        "scores": {
            "overall": sc.overall(),
            "accuracy": sc.accuracy.score,
            "legal_safety": sc.legal_safety.score,
            "prompt_quality": sc.prompt_quality.score,
            "verbosity": sc.verbosity.score,
            "response_quality": sc.response_quality.score,
            "user_interaction": sc.user_interaction.score,
            "monetization_fit": sc.monetization_fit.score,
        },
        "verdict": sc.verdict(),
        "top_issues": sc.top_issues(),
        "hitl_action_suggestion": sc.verdict(),
    }
    if options:
        card["display"]["options"] = {
            "answer": answer_label,
            "distractors": distractors,
        }
    # add primitive-specific bits that a reviewer needs
    if p.get("primitive") == "how_real_is_it":
        rm = p.get("realism") or {}
        card["realism"] = {
            "assessment": rm.get("assessment"),
            "claim_text": rm.get("claim_text"),
            "grounding_type": rm.get("grounding_type"),
            "experts": [
                {"name": e.get("name"), "class": e.get("source_class")}
                for e in (rm.get("expert_attribution") or [])
            ],
        }
    elif p.get("primitive") == "trivia":
        tm = p.get("trivia_meta") or {}
        card["trivia"] = {
            "category": tm.get("category"),
            "fact_snippet": tm.get("fact_snippet", "")[:200],
        }
    elif (p.get("tier0_meta") or {}).get("source_field"):
        t0 = p["tier0_meta"]
        card["tier0"] = {
            "source_field": t0.get("source_field"),
            "section": t0.get("section"),
            "match_confidence": t0.get("match_confidence"),
        }
    return card


# ---------- orchestrator ----------


@dataclass
class FinalizeResult:
    title: str
    total_prompts: int
    dedup_removed: int
    per_primitive: dict[str, int]
    per_verdict: dict[str, int]
    overall_avg: float
    final_path: str
    review_path: str
    cards_json_path: str = ""
    cards_md_path: str = ""
    ui_path: str = ""


def finalize_title(
    *,
    title: str,
    moments_path: Path | str,
    output_dir: Path,
    generator_outputs: list[Path],
    eval_reports: dict[str, dict] | None = None,
    run_eval: bool = False,
) -> FinalizeResult:
    """eval_reports: optional map of prompt_id -> deterministic-eval report dict.
    run_eval: if True, run the deterministic harness inline against each prompt's sources."""
    if eval_reports is None:
        eval_reports = {}
    scene_lookup = _build_scene_lookup(moments_path)

    # gather all prompts
    all_prompts: list[dict] = []
    for path in generator_outputs:
        if not path.exists():
            continue
        data = json.loads(path.read_text())
        for p in data.get("prompts") or []:
            all_prompts.append(p)

    # run deterministic eval if requested
    if run_eval:
        for p in all_prompts:
            pid = p.get("prompt_id", "")
            if pid in eval_reports:
                continue
            try:
                eval_reports[pid] = deterministic_eval(title, p)
            except Exception as exc:  # noqa: BLE001
                eval_reports[pid] = {"pass": False, "notes": [f"eval_exception:{exc}"]}

    # dedup: group by semantic key, keep highest overall score
    scored: list[tuple[PromptScorecard, dict]] = []
    for p in all_prompts:
        scene_ctx = scene_lookup.get(p.get("scene_index"))
        eval_r = eval_reports.get(p.get("prompt_id", ""))
        sc = score_prompt(
            p,
            scene_context=scene_ctx,
            scene_moderation_severity=(scene_ctx or {}).get("moderation_severity", "none"),
            eval_report=eval_r,
        )
        scored.append((sc, p))

    # dedup
    best_by_key: dict[str, tuple[PromptScorecard, dict]] = {}
    for sc, p in scored:
        key = _semantic_key(p)
        existing = best_by_key.get(key)
        if existing is None or sc.overall() > existing[0].overall():
            best_by_key[key] = (sc, p)
    dedup_removed = len(scored) - len(best_by_key)

    final_prompts: list[dict] = []
    review_cards: list[dict] = []
    slim_cards: list[dict] = []
    per_primitive: dict[str, int] = {}
    per_verdict: dict[str, int] = {"approve": 0, "needs_edit": 0, "reject": 0}
    overall_sum = 0.0
    # Sort: scene order first, then primitive priority (scene_iq > how_real > trivia > cast)
    primitive_order = {"scene_iq": 0, "how_real_is_it": 1, "trivia": 2, "cast": 3}
    for sc, p in sorted(
        best_by_key.values(),
        key=lambda x: (x[1].get("scene_index", 0), primitive_order.get(x[1].get("primitive", ""), 99), -x[0].overall()),
    ):
        scene_ctx = scene_lookup.get(p.get("scene_index"))
        # attach eval block to full record
        enriched = dict(p)
        enriched["_eval"] = sc.as_dict()
        final_prompts.append(enriched)
        review_cards.append(_review_card(p, sc, scene_ctx))
        slim_cards.append(_slim_review_card(p, sc, scene_ctx))
        per_primitive[p.get("primitive", "?")] = per_primitive.get(p.get("primitive", "?"), 0) + 1
        per_verdict[sc.verdict()] = per_verdict.get(sc.verdict(), 0) + 1
        overall_sum += sc.overall()

    overall_avg = round(overall_sum / max(1, len(final_prompts)), 3)

    slug = _slug(title)
    output_dir.mkdir(parents=True, exist_ok=True)
    final_path = output_dir / f"{slug}.final.json"
    review_path = output_dir / f"{slug}.review.json"
    cards_json_path = output_dir / f"{slug}.cards.json"
    cards_md_path = output_dir / f"{slug}.cards.md"

    counts = {
        "total_prompts": len(final_prompts),
        "dedup_removed": dedup_removed,
        "per_primitive": per_primitive,
        "per_verdict": per_verdict,
        "overall_avg_score": overall_avg,
    }
    cards_json_path.write_text(json.dumps({
        "title": title,
        "counts": counts,
        "cards": slim_cards,
    }, indent=2))
    cards_md_path.write_text(_markdown_cards(title, slim_cards, counts))

    # UI bundle — only approved prompts, in the client-contract shape.
    ui_path = output_dir / f"{slug}.ui.json"
    approved_records = [
        next(fp for fp in final_prompts if fp.get("prompt_id") == p.get("prompt_id"))
        for sc, p in best_by_key.values()
        if sc.verdict() == "approve"
    ]
    ui_bundle = emit_ui_bundle(
        title=title,
        prompts=approved_records,
        scene_lookup=scene_lookup,
    )
    ui_path.write_text(json.dumps(ui_bundle, indent=2))

    final_path.write_text(json.dumps({
        "title": title,
        "counts": {
            "total_prompts": len(final_prompts),
            "dedup_removed": dedup_removed,
            "per_primitive": per_primitive,
            "per_verdict": per_verdict,
            "overall_avg_score": overall_avg,
        },
        "prompts": final_prompts,
    }, indent=2))

    review_path.write_text(json.dumps({
        "title": title,
        "instructions": (
            "HITL review. For each card: approve | needs_edit | reject. "
            "'verdict' is the system's suggestion; override as needed. 'top_issues' lists "
            "the automated flags. 'source_url' is the primary citation to spot-check."
        ),
        "counts": {
            "total_prompts": len(review_cards),
            "per_verdict": per_verdict,
            "per_primitive": per_primitive,
        },
        "prompts": review_cards,
    }, indent=2))

    return FinalizeResult(
        title=title,
        total_prompts=len(final_prompts),
        dedup_removed=dedup_removed,
        per_primitive=per_primitive,
        per_verdict=per_verdict,
        overall_avg=overall_avg,
        final_path=str(final_path),
        review_path=str(review_path),
        cards_json_path=str(cards_json_path),
        cards_md_path=str(cards_md_path),
        ui_path=str(ui_path),
    )
