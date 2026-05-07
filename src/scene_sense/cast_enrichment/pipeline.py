"""Cast enrichment — generates real actorFact cards from grounded web research.

Per actor in the title's detected_cast set:
  1. Grounded Google search for "<actor> career breakthrough role"
  2. Fetch reputable sources (Rotten Tomatoes, IMDb, named press)
  3. Extract 1 verbatim fact sentence (length 80-160 chars) about their career
  4. Emit as actorFact keyed to the scene where they first appear

Caches per actor (not per scene) because an actor's career fact doesn't change across scenes.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..realism.config import RealismConfig
from ..realism.gemini_client import GeminiClient
from ..realism.moments import Scene, TitleMoments, load_moments
from ..realism.source_bank import (
    _best_substring_ratio,
    _classify_url,
    _fetch_url_text,
    _fetch_youtube_transcript,
    _resolve_redirect,
    _slug,
)

log = logging.getLogger(__name__)


ACTOR_FACT_SCHEMA = {
    "type": "object",
    "properties": {
        "fact_text": {"type": "string"},
        "verbatim_anchor": {"type": "string"},
        "source_index": {"type": "integer"},
        "usable": {"type": "boolean"},
    },
    "required": ["fact_text", "usable"],
}


ACTOR_FACT_SYSTEM = (
    "You write ONE fact sentence about a specific actor for a CTV pause card. "
    "Use ONLY the provided sources. Never invent.\n"
    "\n"
    "STYLE:\n"
    "- 80-160 chars. One sentence. Specific: named role + film/show + year where possible.\n"
    "- Example: 'Luke Wilson made his breakthrough as a bank robber in 1996's Bottle Rocket, "
    "  Wes Anderson's debut.'\n"
    "- Example: 'Jennifer Coolidge's Stifler's mom role in American Pie (1999) made her the go-to "
    "  comedic scene-stealer.'\n"
    "- Prefer surprising facts (breakthrough, 1st role, Tony-winning play, voice-acting gig) over "
    "  generic filmography counts.\n"
    "- NEVER describe the current scene (e.g. 'Jennifer Coolidge plays Paulette in Legally Blonde').\n"
    "- Focus on the actor's CAREER, not this film.\n"
    "\n"
    "Source rules:\n"
    "- `verbatim_anchor`: 6-20 word span copied VERBATIM from source — pipeline will verify.\n"
    "- If no source supports a clean one-sentence fact, set usable=false."
)


@dataclass
class ActorFact:
    actor_name: str
    fact_text: str
    source_url: str
    source_title: str
    verbatim_anchor: str
    anchor_scene_index: int
    validator_passed: bool
    validator_errors: list[str] = field(default_factory=list)


def _collect_actors(title: TitleMoments, min_appearances: int = 1, top_n_skip: int = 1) -> list[tuple[str, int]]:
    """Return (actor_name, first_scene_index) pairs for notable but not-top-billed actors."""
    freq: Counter[str] = Counter()
    first_scene: dict[str, int] = {}
    for s in title.content_scenes():
        cd = None
        # use structured_data.celebrities when available, otherwise detected_cast
        for name in (s.detected_cast or []):
            if not name:
                continue
            freq[name] += 1
            if name not in first_scene:
                first_scene[name] = s.scene_index
        # also harvest structured celebrities
        # (Scene doesn't carry structured celebrities; we fall back to detected_cast only)
    if not freq:
        return []
    # skip top-N (main leads — user already knows them)
    top_names = {name for name, _ in freq.most_common(top_n_skip)}
    out = []
    for name, count in freq.most_common():
        if name in top_names:
            continue
        if count < min_appearances:
            continue
        out.append((name, first_scene[name]))
    return out


def _research_actor(
    client: GeminiClient, cfg: RealismConfig, *, actor_name: str
) -> tuple[str, str, str, str, str] | None:
    """Returns (fact_text, source_url, source_title, verbatim_anchor, confidence) or None."""
    query = f'"{actor_name}" actor breakthrough role career'
    prompt = (
        f"Run a Google search for: {query}\n"
        "Describe the top 3-6 authoritative results. Never invent URLs."
    )
    grounded = client.grounded(
        namespace="cast_enrich_grounded",
        prompt=prompt,
        system_instruction="Run a targeted web search. Never invent URLs.",
        temperature=0.1,
    )
    # Fetch bodies
    sources: list[dict[str, Any]] = []
    seen: set[str] = set()
    for cit in grounded.get("citations") or []:
        raw = (cit.get("url") or "").strip()
        if not raw:
            continue
        url = _resolve_redirect(raw) or raw
        if url in seen:
            continue
        seen.add(url)
        stype = _classify_url(url)
        if stype == "skip":
            continue
        body = ""
        if stype == "youtube":
            ok, text_or_err, _ = _fetch_youtube_transcript(url)
            body = text_or_err if ok else ""
        else:
            ok, text_or_err = _fetch_url_text(url, cfg.http_timeout_s)
            body = text_or_err if ok else ""
        if not body:
            continue
        # title-grounding: body must mention the actor's name
        if actor_name.lower() not in body.lower():
            continue
        sources.append({"url": url, "title": cit.get("title") or url, "body": body[:6000]})

    if not sources:
        return None

    # Generate the fact
    lines = [f"Actor: {actor_name}", "", "SOURCES:"]
    for i, s in enumerate(sources):
        lines.append(f"[S{i}] {s['title']}\n    url: {s['url']}\n    body: {s['body']}")
    gen_prompt = "\n".join(lines)

    resp = client.structured(
        namespace="cast_enrich_gen",
        prompt=gen_prompt,
        response_schema=ACTOR_FACT_SCHEMA,
        system_instruction=ACTOR_FACT_SYSTEM,
        temperature=0.2,
        model=client.cfg.gemini_model_fast,
    )
    if not resp or not resp.get("usable"):
        return None

    fact = (resp.get("fact_text") or "").strip()
    anchor = (resp.get("verbatim_anchor") or "").strip()
    src_idx = resp.get("source_index", 0)
    if not fact or not isinstance(src_idx, int) or src_idx < 0 or src_idx >= len(sources):
        return None
    src = sources[src_idx]
    # Verify anchor
    if anchor:
        ratio = _best_substring_ratio(anchor, src["body"])
        if ratio < 0.8:
            return None
    return fact, src["url"], src["title"], anchor, "high"


def to_record(*, title: str, actor_fact: ActorFact, scene: Scene, model_used: str) -> dict[str, Any]:
    return {
        "title_id": f"tubi:{_slug(title)}",
        "title": title,
        "scene_index": scene.scene_index,
        "scene_start_time": scene.start_time,
        "scene_end_time": scene.end_time,
        "prompt_id": f"ss:{_slug(title)}:{scene.scene_index}:cast_enrich:{hashlib.sha256(actor_fact.actor_name.encode()).hexdigest()[:10]}",
        "primitive": "cast",
        "surface": ["ctv_pause"],
        "headline": f"Recognize {actor_fact.actor_name.split()[0]}?",
        "body": actor_fact.fact_text,
        "drawer": actor_fact.fact_text,
        "options": None,
        "reveal": None,
        "follow_ups": [],
        "source_citations": [
            {
                "type": "web_article",
                "url": actor_fact.source_url,
                "anchor_text": actor_fact.source_title,
                "confidence": "high",
            }
        ],
        "quality_scores": {},
        "hitl": {"state": "pending", "reviewer": None, "reviewed_at": None, "notes": None},
        "monetization": {
            "eligible": actor_fact.validator_passed, "advertiser_categories": [],
            "excluded_categories": [], "sponsorship_tier": "direct_sold",
        },
        "personalization_hints": {"archetypes": ["cast_career"], "cold_start_weight": 0.7},
        "generated_by": {
            "model": model_used, "prompt_version": "cast-enrich-v0.1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "tier0_meta": {
            "source_field": "cast_enriched",
            "celeb_name": actor_fact.actor_name,
            "verbatim_anchor": actor_fact.verbatim_anchor,
            "validator": {
                "passed": actor_fact.validator_passed,
                "errors": actor_fact.validator_errors,
                "ran_at": datetime.now(timezone.utc).isoformat(),
            },
        },
    }


@dataclass
class CastEnrichSummary:
    title: str
    actors_considered: int
    actors_enriched: int
    output_path: str = ""


def run_cast_enrichment(
    *, cfg: RealismConfig, moments_path: Path | str, max_actors: int = 12
) -> CastEnrichSummary:
    client = GeminiClient(cfg)
    title = load_moments(moments_path)
    scenes_by_index = {s.scene_index: s for s in title.scenes}

    actors = _collect_actors(title, top_n_skip=1)[:max_actors]
    log.info("cast_enrich: %s -> %d actors to research", title.title, len(actors))

    records: list[dict[str, Any]] = []
    for actor_name, first_scene_idx in actors:
        scene = scenes_by_index.get(first_scene_idx)
        if not scene:
            continue
        try:
            result = _research_actor(client, cfg, actor_name=actor_name)
        except Exception as exc:  # noqa: BLE001
            log.warning("cast_enrich: %s failed: %s", actor_name, exc)
            continue
        if not result:
            continue
        fact, url, src_title, anchor, confidence = result

        # Validate length
        errors: list[str] = []
        if len(fact) < 50 or len(fact) > 220:
            errors.append(f"fact_length({len(fact)})")

        af = ActorFact(
            actor_name=actor_name, fact_text=fact, source_url=url,
            source_title=src_title, verbatim_anchor=anchor,
            anchor_scene_index=first_scene_idx,
            validator_passed=len(errors) == 0,
            validator_errors=errors,
        )
        records.append(to_record(title=title.title, actor_fact=af, scene=scene, model_used=cfg.gemini_model_fast))

    out_path = cfg.outputs_dir / f"{_slug(title.title)}.cast_enriched.json"
    out_path.write_text(json.dumps({"title": title.title, "prompts": records}, indent=2))
    return CastEnrichSummary(
        title=title.title,
        actors_considered=len(actors),
        actors_enriched=len(records),
        output_path=str(out_path),
    )
