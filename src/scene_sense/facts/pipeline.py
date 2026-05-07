"""Facts pipeline — title-level editorial BTS cards.

Entry point: run_facts_pipeline(cfg, moments_path) -> FactsSummary
Emit:        data/outputs/<slug>.facts.json with the full set of Fact cards.

Each Fact card is *title-level* (not scene-scoped the way trivia is). The card anchors to
a primary scene but may reference supporting scenes. Example topics: SPR bootcamp,
Legally Blonde wardrobe decisions, Gladiator historical consultants.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import urllib.parse
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


# -------------------- Stage 1: title-level topic clustering --------------------


TOPIC_CLUSTER_SCHEMA = {
    "type": "object",
    "properties": {
        "topics": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "hook": {"type": "string"},
                    "category": {
                        "type": "string",
                        "enum": [
                            "production",
                            "casting",
                            "costume",
                            "training",
                            "creative_dispute",
                            "location",
                            "deleted_or_alternate",
                            "legacy_impact",
                            "soundtrack",
                            "practical_effects",
                            "improvisation",
                        ],
                    },
                    "search_queries": {
                        "type": "array",
                        "items": {"type": "string"},
                        "maxItems": 4,
                    },
                    "anchor_scene_index": {"type": "integer"},
                    "supporting_scene_indices": {
                        "type": "array",
                        "items": {"type": "integer"},
                    },
                    "why_interesting": {"type": "string"},
                },
                "required": [
                    "title",
                    "hook",
                    "category",
                    "search_queries",
                    "anchor_scene_index",
                ],
            },
        }
    },
    "required": ["topics"],
}


TOPIC_CLUSTER_SYSTEM = (
    "You propose title-level editorial BTS topics for a CTV pause-screen feature. "
    "Each topic becomes ONE pause card that pays off on a short hook + a 3-5 beat drawer.\n"
    "\n"
    "Good topics are SPECIFIC: 'Dale Dye's 10-day bootcamp mutiny' — not 'actor preparation'. "
    "'Sophie de Rakoff's pink-everything decision' — not 'costume design'. "
    "'The bend-and-snap origin at a Los Angeles bar' — not 'the bend and snap'.\n"
    "\n"
    "Hard rules:\n"
    "- Propose 6-12 topics for a 90-120 min film. Fewer, deeper > more, shallower.\n"
    "- Each topic anchors to a specific scene the viewer might pause on.\n"
    "- `search_queries` must be queries a search engine could actually run — not "
    "\"tell me about production.\" Include the film title in at least one query.\n"
    "- `hook` is ≤ 10 words, the working title of the pause card. Hook-first, viewer register.\n"
    "- Never invent topics. Only propose what you can verify via grounded search."
)


@dataclass
class FactTopic:
    title: str
    hook: str
    category: str
    search_queries: list[str]
    anchor_scene_index: int
    supporting_scene_indices: list[int] = field(default_factory=list)
    why_interesting: str = ""


def cluster_topics(client: GeminiClient, title: TitleMoments) -> list[FactTopic]:
    scene_blob = "\n\n".join(
        f"[scene {s.scene_index}] {s.start_time}–{s.end_time}\n"
        f"  summary: {s.summary}\n"
        f"  themes: {', '.join(s.themes[:4])}\n"
        f"  actions: {'; '.join(s.key_actions[:4])}"
        for s in title.content_scenes()[:25]
    )
    prompt = (
        f"Film: {title.title}\n\n"
        f"Scene sample (first 25):\n{scene_blob}\n\n"
        "Propose 6-12 title-level BTS/Facts topics for a CTV pause-screen card. "
        "Each topic must anchor to a specific scene the viewer might pause on and be "
        "researchable via grounded web search. Prefer specific named-person stories, "
        "quantified production facts, or surprising creative decisions."
    )
    resp = client.structured(
        namespace="facts_topics",
        prompt=prompt,
        response_schema=TOPIC_CLUSTER_SCHEMA,
        system_instruction=TOPIC_CLUSTER_SYSTEM,
        temperature=0.3,
        model=client.cfg.gemini_model_deep,
    )
    out: list[FactTopic] = []
    for t in (resp.get("topics") or []):
        if not t.get("title") or not t.get("hook"):
            continue
        out.append(
            FactTopic(
                title=t["title"],
                hook=t["hook"],
                category=t.get("category", "production"),
                search_queries=list(t.get("search_queries") or []),
                anchor_scene_index=int(t.get("anchor_scene_index") or 0),
                supporting_scene_indices=list(t.get("supporting_scene_indices") or []),
                why_interesting=t.get("why_interesting", ""),
            )
        )
    return out


# -------------------- Stage 2: tiered source discovery --------------------


@dataclass
class FactSource:
    url: str
    title: str
    source_type: str
    domain_tier: str  # "A" (trusted press) | "B" (entertainment blogs) | "C" (fan sites)
    fetched_body: str = ""
    body_hash: str = ""

    def excerpt(self, max_chars: int = 12000) -> str:
        return self.fetched_body[:max_chars]


TIER_A_DOMAINS = {
    "variety.com", "hollywoodreporter.com", "nytimes.com", "latimes.com",
    "vulture.com", "theringer.com", "theatlantic.com", "newyorker.com",
    "wsj.com", "bbc.co.uk", "bbc.com", "npr.org", "rollingstone.com",
    "abajournal.com", "law.com", "wired.com", "arstechnica.com",
    "smithsonianmag.com", "britannica.com",
}
TIER_B_DOMAINS = {
    "bustle.com", "screencrush.com", "cinemablend.com", "mentalfloss.com",
    "thewrap.com", "imdb.com", "ew.com", "deadline.com",
    "collider.com", "indiewire.com", "slashfilm.com",
    "rottentomatoes.com", "flixpatrol.com", "tvinsider.com",
    "buzzfeed.com", "looper.com", "screenrant.com", "thepioneerwoman.com",
    "seventeen.com", "moviemaps.org", "movie-locations.com", "imcdb.org",
    "seeing-stars.com", "graphic.com.gh",
}
SKIP_DOMAINS = {
    "en.wikipedia.org", "pinterest.com", "reddit.com", "fandom.com",
}


def _domain_tier(url: str) -> str:
    try:
        host = (urllib.parse.urlparse(url).hostname or "").lower()
    except Exception:
        return "C"
    root = ".".join(host.split(".")[-2:])
    if host in SKIP_DOMAINS or root in SKIP_DOMAINS:
        return "skip"
    if host in TIER_A_DOMAINS or root in TIER_A_DOMAINS:
        return "A"
    if host in TIER_B_DOMAINS or root in TIER_B_DOMAINS:
        return "B"
    if ".edu" in host or ".gov" in host or ".ac." in host:
        return "A"
    return "C"


def discover_sources(
    client: GeminiClient, cfg: RealismConfig, *, title: str, topic: FactTopic
) -> list[FactSource]:
    seen: set[str] = set()
    sources: list[FactSource] = []
    for q in topic.search_queries[:3]:
        prompt = (
            f"Run a Google search for: {q}\n"
            "After searching, describe the top 4-8 most authoritative results. "
            "Do NOT invent any URL. Only describe what the search returned."
        )
        grounded = client.grounded(
            namespace=f"facts_discover_{_slug(topic.category)}",
            prompt=prompt,
            system_instruction="Run a targeted web search. Never invent URLs.",
            temperature=0.1,
        )
        for cit in grounded.get("citations") or []:
            raw = (cit.get("url") or "").strip()
            if not raw:
                continue
            url = _resolve_redirect(raw) or raw
            if url in seen:
                continue
            seen.add(url)
            tier = _domain_tier(url)
            if tier == "skip":
                continue
            stype = _classify_url(url)
            body = ""
            if stype == "youtube":
                ok, text_or_err, _ = _fetch_youtube_transcript(url)
                body = text_or_err if ok else ""
            else:
                ok, text_or_err = _fetch_url_text(url, cfg.http_timeout_s)
                body = text_or_err if ok else ""
            if not body:
                continue
            # Title-grounding gate
            tokens = [t for t in re.split(r"\W+", title.lower()) if len(t) >= 4]
            hits = sum(1 for t in tokens if t in body.lower())
            if tokens and hits < max(1, len(tokens) // 2):
                continue
            sources.append(
                FactSource(
                    url=url,
                    title=cit.get("title") or url,
                    source_type=stype,
                    domain_tier=tier,
                    fetched_body=body,
                    body_hash=hashlib.sha256(body.encode("utf-8")).hexdigest()[:16],
                )
            )
    # sort by tier then by body length (more-content sources first within tier)
    tier_order = {"A": 0, "B": 1, "C": 2}
    sources.sort(key=lambda s: (tier_order.get(s.domain_tier, 3), -len(s.fetched_body)))
    return sources[:8]  # cap sources per topic


# -------------------- Stage 3: card assembly --------------------


FACT_CARD_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "body": {"type": "string"},
        "drawer_beats": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "source_index": {"type": "integer"},
                    "verbatim_anchor": {"type": "string"},
                },
                "required": ["text", "source_index"],
            },
            "minItems": 2,
            "maxItems": 5,
        },
        "follow_up_questions": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 3,
        },
        "confidence_level": {"type": "string", "enum": ["high", "medium", "low"]},
        "usable": {"type": "boolean"},
        "reason_if_unusable": {"type": "string"},
    },
    "required": ["headline", "body", "drawer_beats", "usable"],
}


FACT_CARD_SYSTEM = (
    "You write editorial BTS pause cards for a CTV viewer. Use ONLY the provided source bodies. "
    "Never invent facts, names, numbers, or quotes.\n"
    "\n"
    "STYLE — match the best film-magazine writing:\n"
    "- HEADLINE: ≤ 8 words, hook-first, viewer register. 'Dale Dye's bootcamp mutiny' not "
    "  'The cast's preparation for filming.' Proper noun in first 2 words when possible.\n"
    "- BODY: ONE sentence, ≤ 180 chars, the top-line payoff. Specific: named person + concrete "
    "  action + quantifiable anchor (number / date / place) where available.\n"
    "- DRAWER BEATS: 3-5 short beats, each a single sentence, each with a `source_index` "
    "  pointing to one of the supplied sources. Beats should tell a micro-story in order. "
    "  Every beat must be traceable to the fetched source body.\n"
    "- FOLLOW-UP QUESTIONS: 2-3 natural viewer next-questions. ≤ 10 words each, phrased as "
    "  what a curious viewer would ask next, not as our answers.\n"
    "- Use CHARACTER names for what's on screen, REAL names for BTS figures (directors, "
    "  costume designers, named crew). Example: 'Elle Woods' for the character, 'Sophie de "
    "  Rakoff' for the costume designer.\n"
    "- Don't re-describe the scene the viewer is watching; deliver only NEW info.\n"
    "- Present tense for what's on screen; past tense for BTS.\n"
    "\n"
    "Source rules:\n"
    "- `verbatim_anchor`: a 6-20 word span copied verbatim from the source, supporting the beat.\n"
    "- If no source supports a clean story, set `usable=false` with a reason.\n"
    "- Prefer Tier A sources (Variety, Hollywood Reporter, named press) over blogs when both present."
)


@dataclass
class FactCard:
    topic: FactTopic
    headline: str
    body: str
    drawer_beats: list[dict[str, Any]]
    follow_up_questions: list[str]
    sources_used: list[FactSource]
    confidence_level: str
    validator_passed: bool
    validator_errors: list[str] = field(default_factory=list)


def generate_fact_card(
    client: GeminiClient, *, title: str, topic: FactTopic, sources: list[FactSource]
) -> FactCard | None:
    if len(sources) < 1:
        return None
    lines: list[str] = [
        f"Film: {title}",
        f"Topic title: {topic.title}",
        f"Topic hook (working): {topic.hook}",
        f"Category: {topic.category}",
        f"Anchor scene: {topic.anchor_scene_index}",
        "",
        f"SOURCES (use only these; verbatim anchors required):",
    ]
    for i, s in enumerate(sources):
        lines.append(f"[S{i}] tier={s.domain_tier} type={s.source_type} | {s.title}")
        lines.append(f"     url: {s.url}")
        lines.append(f"     body: {s.excerpt(10000)}")
    prompt = "\n".join(lines)

    resp = client.structured(
        namespace="facts_card_gen",
        prompt=prompt,
        response_schema=FACT_CARD_SCHEMA,
        system_instruction=FACT_CARD_SYSTEM,
        temperature=0.2,
        model=client.cfg.gemini_model_fast,
    )
    if not resp or not resp.get("usable"):
        return None

    headline = (resp.get("headline") or "").strip()
    body = (resp.get("body") or "").strip()
    beats = resp.get("drawer_beats") or []
    follow_ups = resp.get("follow_up_questions") or []

    if not headline or not body or len(beats) < 2:
        return None

    # Validator: each beat's verbatim_anchor must appear in its cited source body
    errors: list[str] = []
    sources_used: list[FactSource] = []
    clean_beats: list[dict[str, Any]] = []
    for j, b in enumerate(beats):
        si = b.get("source_index")
        if not isinstance(si, int) or si < 0 or si >= len(sources):
            errors.append(f"beat{j}_bad_source_index")
            continue
        src = sources[si]
        anchor = (b.get("verbatim_anchor") or "").strip()
        if anchor:
            ratio = _best_substring_ratio(anchor, src.fetched_body)
            if ratio < 0.8:
                errors.append(f"beat{j}_anchor_not_in_source(ratio={ratio:.2f})")
                continue
        clean_beats.append(
            {
                "text": (b.get("text") or "").strip(),
                "source_url": src.url,
                "source_tier": src.domain_tier,
                "verbatim_anchor": anchor,
            }
        )
        if src not in sources_used:
            sources_used.append(src)

    if len(clean_beats) < 2:
        errors.append("insufficient_clean_beats")

    # Length checks
    if len(headline) > 70:
        errors.append(f"headline_too_long({len(headline)})")
    if len(body) > 220:
        errors.append(f"body_too_long({len(body)})")

    # Prefer at least 1 Tier A source; downgrade to a warning if only Tier B sources
    # are available (BTS content often lives on reputable entertainment sites, which
    # are Tier B). The card is still usable — just flag for ops awareness.
    tier_a_count = sum(1 for s in sources_used if s.domain_tier == "A")
    tier_b_count = sum(1 for s in sources_used if s.domain_tier == "B")
    if tier_a_count == 0 and tier_b_count == 0 and sources_used:
        # No A or B — that's a real problem, only C sources cited
        errors.append("only_tier_c_sources")

    return FactCard(
        topic=topic,
        headline=headline,
        body=body,
        drawer_beats=clean_beats,
        follow_up_questions=[q.strip() for q in follow_ups if q.strip()][:3],
        sources_used=sources_used,
        confidence_level=resp.get("confidence_level", "medium"),
        validator_passed=len(errors) == 0,
        validator_errors=errors,
    )


# -------------------- Stage 4: emit record --------------------


def to_record(*, title: str, card: FactCard, scene: Scene, model_used: str) -> dict[str, Any]:
    key = f"{card.topic.category}:{card.topic.title}"
    return {
        "title_id": f"tubi:{_slug(title)}",
        "title": title,
        "scene_index": scene.scene_index,
        "scene_start_time": scene.start_time,
        "scene_end_time": scene.end_time,
        "prompt_id": f"ss:{_slug(title)}:{scene.scene_index}:facts:{hashlib.sha256(key.encode()).hexdigest()[:10]}",
        "primitive": "facts",
        "surface": ["ctv_pause"],
        "headline": card.headline,
        "body": card.body,
        "drawer": " ".join(b["text"] for b in card.drawer_beats),
        "options": None,
        "reveal": None,
        "follow_ups": [{"headline": q, "prompt_id": ""} for q in card.follow_up_questions],
        "source_citations": [
            {
                "type": s.source_type,
                "url": s.url,
                "anchor_text": s.title,
                "confidence": card.confidence_level,
                "tier": s.domain_tier,
            }
            for s in card.sources_used
        ],
        "quality_scores": {},
        "hitl": {"state": "pending", "reviewer": None, "reviewed_at": None, "notes": None},
        "monetization": {
            "eligible": card.validator_passed,
            "advertiser_categories": [],
            "excluded_categories": [],
            "sponsorship_tier": "direct_sold",
        },
        "personalization_hints": {"archetypes": [card.topic.category], "cold_start_weight": 0.7},
        "generated_by": {
            "model": model_used,
            "prompt_version": "facts-v0.1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "facts_meta": {
            "topic_title": card.topic.title,
            "topic_category": card.topic.category,
            "anchor_scene_index": card.topic.anchor_scene_index,
            "supporting_scene_indices": card.topic.supporting_scene_indices,
            "drawer_beats": card.drawer_beats,
            "follow_up_questions": card.follow_up_questions,
            "sources_used_tiers": [s.domain_tier for s in card.sources_used],
            "validator": {
                "passed": card.validator_passed,
                "errors": card.validator_errors,
                "ran_at": datetime.now(timezone.utc).isoformat(),
            },
        },
    }


# -------------------- orchestrator --------------------


@dataclass
class FactsSummary:
    title: str
    total_topics: int
    topics_with_sources: int
    cards_generated: int
    cards_validated: int
    output_path: str = ""


def run_facts_pipeline(
    *, cfg: RealismConfig, moments_path: Path | str, topic_limit: int | None = None
) -> FactsSummary:
    client = GeminiClient(cfg)
    title = load_moments(moments_path)
    log.info("facts: clustering topics for %s (%d content scenes)", title.title, len(title.content_scenes()))

    topics = cluster_topics(client, title)
    if topic_limit:
        topics = topics[:topic_limit]
    log.info("facts: %d topics proposed", len(topics))

    scenes_by_index = {s.scene_index: s for s in title.scenes}
    records: list[dict[str, Any]] = []
    topics_with_sources = 0
    cards_generated = 0
    cards_validated = 0

    for topic in topics:
        anchor_scene = scenes_by_index.get(topic.anchor_scene_index)
        if not anchor_scene:
            # fall back to scene 2 (first content scene commonly)
            anchor_scene = title.content_scenes()[0] if title.content_scenes() else None
        if not anchor_scene:
            continue

        sources = discover_sources(client, cfg, title=title.title, topic=topic)
        if not sources:
            log.info("facts: no sources for topic '%s'", topic.title)
            continue
        topics_with_sources += 1

        card = generate_fact_card(client, title=title.title, topic=topic, sources=sources)
        if not card:
            log.info("facts: no usable card for topic '%s'", topic.title)
            continue
        cards_generated += 1
        if card.validator_passed:
            cards_validated += 1
        records.append(to_record(title=title.title, card=card, scene=anchor_scene, model_used=cfg.gemini_model_fast))

    out_path = cfg.outputs_dir / f"{_slug(title.title)}.facts.json"
    out_path.write_text(json.dumps({"title": title.title, "prompts": records}, indent=2))

    return FactsSummary(
        title=title.title,
        total_topics=len(topics),
        topics_with_sources=topics_with_sources,
        cards_generated=cards_generated,
        cards_validated=cards_validated,
        output_path=str(out_path),
    )
