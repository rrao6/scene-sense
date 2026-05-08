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
import logging
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

from ..curiosity_judge.judge import judge_card
from ..realism.config import RealismConfig
from ..realism.gemini_client import GeminiClient
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
    """Dedup key. Now scene-AGNOSTIC for fact-type cards so Il-Cielo-in-two-scenes collides.

    Three strategies:
      - cast primitive: key on actor name only (one card per actor, any scene)
      - trivia: key on correct_answer + primitive (same answer across scenes = dup)
      - other fact types: normalized headline+body hash, scene-agnostic
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

    # Correct-answer dedup for trivia: same answer across scenes = same card
    if primitive == "trivia":
        correct = ""
        for o in (p.get("options") or []):
            if o.get("correct"):
                correct = (o.get("label") or "").lower().strip()
                break
        ans_norm = re.sub(r"[^a-z0-9 ]+", " ", correct)
        ans_norm = re.sub(r"\s+", " ", ans_norm).strip()
        digest = hashlib.sha256(ans_norm.encode()).hexdigest()[:12]
        return f"trivia:answer:{digest}"

    # Other fact-type cards: headline+body, scene-agnostic (catches Il Cielo-in-2-scenes)
    text = (p.get("headline", "") + " " + p.get("body", "")).lower()
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    STOPFILL = {
        "the","a","an","is","was","were","in","of","that","this","to","for","on","at","by",
        "when","what","who","which","where","how","does","did","do","your","her","his","their",
        "scene","this","film","movie",
        "also","just","really","actually","about","with","from",
    }
    tokens = [t for t in text.split() if t and t not in STOPFILL and len(t) > 1]
    normalized = " ".join(sorted(tokens)[:20])
    digest = hashlib.sha256(normalized.encode()).hexdigest()[:12]
    return f"{primitive}:{digest}"


def _subject_of(p: dict, scene_lookup: dict[int, dict] | None = None) -> str | None:
    """Extract the primary subject of a card (actor name, BTS figure) for capping.

    Returns None if no identifiable subject (e.g. a location-only card).
    """
    primitive = p.get("primitive", "")
    if primitive == "cast":
        t0 = p.get("tier0_meta") or {}
        return (t0.get("celeb_name") or "").strip().lower() or None

    # Trivia / facts / hriv2: look for the correct-answer or a named subject in body/drawer
    text_fields = [p.get("body") or "", p.get("drawer") or "", p.get("headline") or ""]
    # Check options for cast_career
    options = p.get("options") or []
    if options:
        correct = next((o.get("label", "") for o in options if o.get("correct")), "")
        if correct and re.fullmatch(r"[A-Z][A-Za-z'\.\-]+(?:\s+[A-Z][A-Za-z'\.\-]+){1,3}", correct.strip()):
            return correct.strip().lower()
    # Fall back to first proper-name run in body
    for text in text_fields:
        m = re.search(r"\b([A-Z][A-Za-z'\.\-]+(?:\s+[A-Z][A-Za-z'\.\-]+){1,3})\b", text)
        if m:
            candidate = m.group(1).strip()
            tokens = candidate.split()
            STOP = {"The","A","An","In","At","On","By","Elle","Warner","Legally","Blonde",
                    "Harvard","Stanford","Delta","Nu"}
            if all(t not in STOP for t in tokens) and len(tokens) >= 2:
                return candidate.lower()
    return None


def _apply_subject_cap(items: list[tuple["PromptScorecard", dict]],
                       max_per_subject: int = 1) -> list[tuple["PromptScorecard", dict]]:
    """Cap cards per subject. Keeps highest-scored card for each subject."""
    # Sort by score descending so best card per subject survives
    items = sorted(items, key=lambda x: -x[0].overall())
    seen: dict[str, int] = {}
    kept = []
    for sc, p in items:
        subj = _subject_of(p)
        if not subj:
            kept.append((sc, p))
            continue
        count = seen.get(subj, 0)
        if count < max_per_subject:
            kept.append((sc, p))
            seen[subj] = count + 1
        else:
            log.info("subject_cap: dropped card about '%s' (already have %d)",
                     subj[:40], count)
    return kept


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
    run_judge: bool = False,
    cfg: RealismConfig | None = None,
    rank_caps: dict[str, int] | None = None,
) -> FinalizeResult:
    """
    rank_caps: optional per-primitive cap, e.g. {"trivia": 20, "facts": 10, "how_real_is_it": 12}.
               After dedup + subject cap, sorts by overall score and keeps top N per primitive.
    """
    """eval_reports: optional map of prompt_id -> deterministic-eval report dict.
    run_eval: if True, run the deterministic harness inline against each prompt's sources.
    run_judge: if True, run the curiosity judge on each prompt (viewer-voice scorer).
    cfg: required if run_judge is True (for the Gemini client)."""
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

    # run curiosity judge if requested
    judgments: dict[str, dict] = {}
    if run_judge and cfg is not None:
        judge_client = GeminiClient(cfg)
        for p in all_prompts:
            pid = p.get("prompt_id", "")
            if not pid or pid in judgments:
                continue
            scene_ctx = scene_lookup.get(p.get("scene_index"))
            j = judge_card(judge_client, cfg, p, scene_context=scene_ctx)
            if j is not None:
                judgments[pid] = j.as_dict()

    # dedup: group by semantic key, keep highest overall score
    scored: list[tuple[PromptScorecard, dict]] = []
    for p in all_prompts:
        scene_ctx = scene_lookup.get(p.get("scene_index"))
        eval_r = eval_reports.get(p.get("prompt_id", ""))
        curiosity_j = judgments.get(p.get("prompt_id", ""))
        sc = score_prompt(
            p,
            scene_context=scene_ctx,
            scene_moderation_severity=(scene_ctx or {}).get("moderation_severity", "none"),
            eval_report=eval_r,
            curiosity_judgment=curiosity_j,
        )
        scored.append((sc, p))

    # Stage 1: dedup by semantic key
    best_by_key: dict[str, tuple[PromptScorecard, dict]] = {}
    for sc, p in scored:
        key = _semantic_key(p)
        existing = best_by_key.get(key)
        if existing is None or sc.overall() > existing[0].overall():
            best_by_key[key] = (sc, p)
    dedup_removed = len(scored) - len(best_by_key)

    # Stage 2: subject cap (max 1 card per non-lead actor / BTS figure)
    # Run within each primitive separately so e.g. cast enriched + cast_career trivia
    # can both mention the same actor once.
    capped_items: list[tuple[PromptScorecard, dict]] = []
    items_by_prim: dict[str, list[tuple[PromptScorecard, dict]]] = {}
    for sc, p in best_by_key.values():
        items_by_prim.setdefault(p.get("primitive", "?"), []).append((sc, p))
    for prim, items in items_by_prim.items():
        # cast primitive already dedups per-actor via semantic key
        if prim == "cast":
            capped_items.extend(items)
            continue
        capped = _apply_subject_cap(items, max_per_subject=1)
        capped_items.extend(capped)
    subject_cap_removed = len(best_by_key) - len(capped_items)
    log.info("finalize: dedup removed %d, subject_cap removed %d", dedup_removed, subject_cap_removed)

    # Rebuild best_by_key with capped items for downstream code
    best_by_key = {p.get("prompt_id", f"id{i}"): (sc, p) for i, (sc, p) in enumerate(capped_items)}

    # Stage 3: per-primitive top-N ranking (ship only top N by score)
    if rank_caps:
        by_prim: dict[str, list[tuple[PromptScorecard, dict]]] = {}
        for sc, p in capped_items:
            by_prim.setdefault(p.get("primitive", "?"), []).append((sc, p))
        ranked: list[tuple[PromptScorecard, dict]] = []
        for prim, items in by_prim.items():
            cap = rank_caps.get(prim, 999)
            # Sort by overall score descending; keep top `cap`
            items_sorted = sorted(items, key=lambda x: -x[0].overall())
            kept = items_sorted[:cap]
            ranked.extend(kept)
            if len(items_sorted) > cap:
                log.info("rank_cap: %s kept %d of %d by score", prim, cap, len(items_sorted))
        best_by_key = {p.get("prompt_id", f"id{i}"): (sc, p) for i, (sc, p) in enumerate(ranked)}

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
