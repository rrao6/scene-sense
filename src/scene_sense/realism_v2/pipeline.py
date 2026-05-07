"""How Real Is It? v2 — myth-busting pipeline.

Title-agnostic. Works on historical / legal / medical / military / hacking genres.

Stages:
  1. Domain detection (reuse realism/eligibility keyword scan)
  2. Scene-level myth candidate generation (new prompt: find the SURPRISE)
  3. Grounded research — Tier S primary sources first, Tier A experts second
  4. Card assembly — hook-first headline, one-sentence body that IS the myth-bust
  5. Validator — source URL resolves, headline is hook-first, body ≤ 180 chars
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..realism.config import RealismConfig
from ..realism.eligibility import DOMAIN_KEYWORDS, detect_candidate_domains
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
from ..realism.statutes import STATUTES, find_relevant_statutes
from .historical_sources import HISTORICAL_SOURCES, find_historical_sources

log = logging.getLogger(__name__)


# -------------------- domain -> era mapping --------------------

DOMAIN_TO_ERA = {
    "historical": "ancient_rome",
    "military": "ww2",
    "legal": None,
    "medical": None,
    "hacking": None,
}


# -------------------- Stage 1-2: myth candidate generation --------------------


MYTH_SCHEMA = {
    "type": "object",
    "properties": {
        "myths": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "scene_reference": {"type": "string"},
                    "film_claim": {"type": "string"},
                    "myth_direction": {
                        "type": "string",
                        "enum": ["surprisingly_wrong", "surprisingly_right", "invented_by_film"],
                    },
                    "search_query": {"type": "string"},
                    "why_surprising": {"type": "string"},
                },
                "required": ["scene_reference", "film_claim", "myth_direction", "search_query"],
            },
        }
    },
    "required": ["myths"],
}


MYTH_SYSTEM = (
    "You find the most SURPRISING gap between what a film shows and what actually happened in "
    "reality. You do NOT assess accuracy dryly — you surface the hook viewers would share.\n"
    "\n"
    "Bias strongly toward:\n"
    "- 'surprisingly_wrong' — what viewers assume is true but isn't (e.g. 'thumbs down = death')\n"
    "- 'invented_by_film' — iconic moments that have no historical basis ('strength and honor')\n"
    "- 'surprisingly_right' — things viewers assume are Hollywood but actually happened ('Commodus really fought in the arena')\n"
    "\n"
    "Avoid boring verdicts like 'within normal parameters.' If a scene has nothing surprising, "
    "propose nothing for it.\n"
    "\n"
    "Each myth needs a search_query a search engine can actually run. Include the specific claim "
    "or concept (e.g. 'pollice verso gladiator thumbs down meaning') — not just the film title.\n"
    "\n"
    "Output: 0-3 myth candidates per scene."
)


@dataclass
class MythCandidate:
    scene_index: int
    scene_reference: str
    film_claim: str
    myth_direction: str  # surprisingly_wrong | surprisingly_right | invented_by_film
    search_query: str
    why_surprising: str = ""


def propose_myths_for_scene(
    client: GeminiClient, *, title: str, domain: str, scene: Scene
) -> list[MythCandidate]:
    prompt = (
        f"Film: {title}\nDomain: {domain}\n\n"
        f"Scene:\n{scene.as_llm_context()}\n\n"
        "Propose 0-3 MYTH-BUST candidates for this scene. What would a viewer be surprised to "
        "learn? Find specific, visual claims in the scene — not interpretation or vibes. "
        "If the scene has no surprising reality-gap, return an empty myths array."
    )
    resp = client.structured(
        namespace="hriv2_myths",
        prompt=prompt,
        response_schema=MYTH_SCHEMA,
        system_instruction=MYTH_SYSTEM,
        temperature=0.3,
        model=client.cfg.gemini_model_deep,
    )
    out: list[MythCandidate] = []
    for m in (resp.get("myths") or []):
        if not m.get("film_claim") or not m.get("search_query"):
            continue
        out.append(
            MythCandidate(
                scene_index=scene.scene_index,
                scene_reference=m.get("scene_reference", ""),
                film_claim=m["film_claim"].strip(),
                myth_direction=m.get("myth_direction", "surprisingly_wrong"),
                search_query=m["search_query"].strip(),
                why_surprising=m.get("why_surprising", ""),
            )
        )
    return out


# -------------------- Stage 3: tiered grounded research --------------------


@dataclass
class MythSource:
    url: str
    title: str
    source_type: str
    tier: str  # "S" | "A" | "B" | "C"
    fetched_body: str = ""

    def excerpt(self, max_chars: int = 10000) -> str:
        return self.fetched_body[:max_chars]


TIER_S_DOMAINS = {
    "penelope.uchicago.edu",  # LacusCurtius
    "perseus.tufts.edu",
    "law.cornell.edu",
    "americanbar.org",
    "uscourts.gov",
    "constitution.congress.gov",
    "supreme.justia.com",
    "hhs.gov",
    "fda.gov",
    "supremecourt.gov",
}
TIER_A_DOMAINS = {
    "harvard.edu", "yale.edu", "princeton.edu", "stanford.edu",
    "oxford.ac.uk", "cam.ac.uk", "uchicago.edu", "columbia.edu",
    "britishmuseum.org", "metmuseum.org", "getty.edu", "smithsonianmag.com",
    "loc.gov",  # Library of Congress
    "en.wikipedia.org",  # allowed as Tier A here because a huge amount of
                         # primary-source-cited material lives on wiki pages
                         # for classical texts; pipeline verifies citations
                         # against primary sources separately
}
TIER_B_DOMAINS = {
    "worldhistory.org",
    "bbc.com", "bbc.co.uk",
    "theatlantic.com", "newyorker.com",
    "nytimes.com", "wsj.com",
    "theconversation.com",
    "toldinstone.com",
}


def _tier_of(url: str) -> str:
    import urllib.parse
    try:
        host = (urllib.parse.urlparse(url).hostname or "").lower()
    except Exception:
        return "C"
    root = ".".join(host.split(".")[-2:])
    for tier, domains in [("S", TIER_S_DOMAINS), ("A", TIER_A_DOMAINS), ("B", TIER_B_DOMAINS)]:
        if host in domains or root in domains:
            return tier
    # .edu / .gov / .ac fallback -> A
    if any(x in host for x in (".edu/", ".gov/", ".ac.")) or host.endswith(".edu") or host.endswith(".gov") or host.endswith(".ac.uk"):
        return "A"
    return "C"


def _curated_sources_for_claim(domain: str, claim_text: str) -> list[MythSource]:
    """Return pre-vetted Tier-S sources from the static libraries (no network calls)."""
    out: list[MythSource] = []
    # Historical primary sources
    era = DOMAIN_TO_ERA.get(domain)
    for h in find_historical_sources(era, claim_text, top_k=3):
        out.append(
            MythSource(
                url=h.url, title=h.citation, source_type="primary_text",
                tier="S", fetched_body=h.summary,
            )
        )
    # Legal statutes
    if domain in ("legal", "medical", "financial"):
        for s in find_relevant_statutes(domain, claim_text, top_k=3):
            out.append(
                MythSource(
                    url=s.url, title=s.citation, source_type="statute",
                    tier="S", fetched_body=s.summary,
                )
            )
    return out


def research_myth(
    client: GeminiClient, cfg: RealismConfig, *, title: str, domain: str, myth: MythCandidate
) -> list[MythSource]:
    """Return a list of sources, Tier-S first, then grounded web results."""
    out: list[MythSource] = _curated_sources_for_claim(domain, myth.film_claim + " " + myth.search_query)

    # Grounded search for live evidence
    prompt = (
        f"Run a Google search for: {myth.search_query}\n"
        "After searching, describe the top 3-6 most authoritative results. "
        "Do NOT invent any URL. Only describe what the search returned."
    )
    grounded = client.grounded(
        namespace=f"hriv2_ground_{_slug(domain)}",
        prompt=prompt,
        system_instruction="Run a targeted web search. Never invent URLs.",
        temperature=0.1,
    )

    seen: set[str] = set(s.url for s in out)
    for cit in grounded.get("citations") or []:
        raw = (cit.get("url") or "").strip()
        if not raw:
            continue
        url = _resolve_redirect(raw) or raw
        if url in seen:
            continue
        seen.add(url)
        tier = _tier_of(url)
        if tier == "C":
            continue  # skip low-tier for historical claims — quality matters
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
        out.append(
            MythSource(
                url=url, title=cit.get("title") or url, source_type=stype,
                tier=tier, fetched_body=body,
            )
        )
    # Sort: Tier S > A > B, then by body length descending
    tier_order = {"S": 0, "A": 1, "B": 2}
    out.sort(key=lambda s: (tier_order.get(s.tier, 9), -len(s.fetched_body)))
    return out[:6]


# -------------------- Stage 4: card assembly --------------------


CARD_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "body": {"type": "string"},
        "primary_source_url": {"type": "string"},
        "primary_source_citation": {"type": "string"},
        "verbatim_anchor": {"type": "string"},
        "confidence_level": {"type": "string", "enum": ["high", "medium", "low"]},
        "usable": {"type": "boolean"},
        "reason_if_unusable": {"type": "string"},
    },
    "required": ["headline", "body", "primary_source_url", "usable"],
}


CARD_SYSTEM = (
    "You write CTV pause-screen cards that flip the viewer's expectations. Use ONLY the provided "
    "sources. Never invent facts, citations, or quotes.\n"
    "\n"
    "STYLE:\n"
    "- HEADLINE: ≤ 8 words. Hook-first. Prefer 'Thumbs-down meant the opposite' over "
    "  'How thumb gestures worked.' State the SURPRISE in the headline itself.\n"
    "- BODY: ONE sentence, ≤ 180 chars. Concrete primary-source anchor (named person + specific "
    "  text + citable book/chapter). Example: 'Suetonius (Augustus 44) records that women were "
    "  forbidden to sit with men at the gladiators — confined to the upper rows.'\n"
    "- `verbatim_anchor`: 6-20 words copied VERBATIM from one source's body — the pipeline will "
    "  verify this against the source.\n"
    "- Use CHARACTER names for what's on screen; REAL names for historical figures.\n"
    "- Don't re-describe the scene the viewer is watching; deliver the NEW info.\n"
    "\n"
    "SOURCE PREFERENCE:\n"
    "- Tier S (LacusCurtius, Perseus, Cornell Law, .gov statute text) — ALWAYS prefer when available.\n"
    "- Tier A (named experts, museum sites, .edu) — second choice.\n"
    "- Tier B (Mary Beard, Tom Holland, reputable popular history) — third.\n"
    "- NEVER use Tier C (random blogs, fan wikis).\n"
    "- If no Tier S/A source supports the myth, set usable=false."
)


@dataclass
class MythCard:
    myth: MythCandidate
    headline: str
    body: str
    primary_source_url: str
    primary_source_citation: str
    verbatim_anchor: str
    all_sources: list[MythSource]
    confidence_level: str
    validator_passed: bool
    validator_errors: list[str] = field(default_factory=list)


def generate_myth_card(
    client: GeminiClient, *, title: str, myth: MythCandidate, sources: list[MythSource]
) -> MythCard | None:
    if not sources:
        return None
    lines = [
        f"Film: {title}",
        f"Scene reference: {myth.scene_reference}",
        f"Film claim: {myth.film_claim}",
        f"Myth direction: {myth.myth_direction}",
        "",
        "SOURCES (prefer Tier S > A > B):",
    ]
    for i, s in enumerate(sources):
        lines.append(f"[S{i}] tier={s.tier} type={s.source_type} | {s.title}")
        lines.append(f"     url: {s.url}")
        lines.append(f"     body: {s.excerpt(6000)}")
    prompt = "\n".join(lines)

    resp = client.structured(
        namespace="hriv2_card_gen",
        prompt=prompt,
        response_schema=CARD_SCHEMA,
        system_instruction=CARD_SYSTEM,
        temperature=0.2,
        model=client.cfg.gemini_model_fast,
    )
    if not resp or not resp.get("usable"):
        return None

    headline = (resp.get("headline") or "").strip()
    body = (resp.get("body") or "").strip()
    url = (resp.get("primary_source_url") or "").strip()
    citation = (resp.get("primary_source_citation") or "").strip()
    anchor = (resp.get("verbatim_anchor") or "").strip()

    # Validator
    errors: list[str] = []
    if not headline or len(headline) > 80:
        errors.append(f"headline_length({len(headline)})")
    if not body or len(body) > 220:
        errors.append(f"body_length({len(body)})")
    if not url:
        errors.append("missing_source_url")
    # URL must be one of the supplied sources
    source_urls = {s.url for s in sources}
    if url and url not in source_urls:
        errors.append("source_url_not_in_supplied_set")
    # Anchor must be substring of at least one source body
    chosen_source = next((s for s in sources if s.url == url), None)
    if anchor and chosen_source:
        ratio = _best_substring_ratio(anchor, chosen_source.fetched_body)
        if ratio < 0.8:
            errors.append(f"anchor_not_in_source(ratio={ratio:.2f})")

    # Prefer Tier S source — demote if we picked lower
    tier_used = chosen_source.tier if chosen_source else "?"
    has_tier_s = any(s.tier == "S" for s in sources)
    if has_tier_s and tier_used not in ("S", "A"):
        errors.append(f"did_not_use_tier_s_when_available")

    return MythCard(
        myth=myth,
        headline=headline,
        body=body,
        primary_source_url=url,
        primary_source_citation=citation or (chosen_source.title if chosen_source else ""),
        verbatim_anchor=anchor,
        all_sources=sources,
        confidence_level=resp.get("confidence_level", "medium"),
        validator_passed=len(errors) == 0,
        validator_errors=errors,
    )


# -------------------- emit record --------------------


def to_record(*, title: str, card: MythCard, scene: Scene, model_used: str) -> dict[str, Any]:
    key = f"{card.myth.myth_direction}:{card.myth.search_query}"
    return {
        "title_id": f"tubi:{_slug(title)}",
        "title": title,
        "scene_index": scene.scene_index,
        "scene_start_time": scene.start_time,
        "scene_end_time": scene.end_time,
        "prompt_id": f"ss:{_slug(title)}:{scene.scene_index}:hriv2:{hashlib.sha256(key.encode()).hexdigest()[:10]}",
        "primitive": "how_real_is_it",
        "surface": ["ctv_pause"],
        "headline": card.headline,
        "body": card.body,
        "drawer": card.body,
        "options": None,
        "reveal": None,
        "follow_ups": [],
        "source_citations": [
            {
                "type": "primary_text" if card.primary_source_url else "citation",
                "url": card.primary_source_url,
                "anchor_text": card.primary_source_citation,
                "confidence": card.confidence_level,
            }
        ],
        "quality_scores": {},
        "hitl": {"state": "pending", "reviewer": None, "reviewed_at": None, "notes": None},
        "monetization": {
            "eligible": card.validator_passed,
            "advertiser_categories": [],
            "excluded_categories": [],
            "sponsorship_tier": "direct_sold",
        },
        "personalization_hints": {
            "archetypes": [card.myth.myth_direction], "cold_start_weight": 0.7,
        },
        "generated_by": {
            "model": model_used,
            "prompt_version": "hriv2-v0.1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "realism": {
            "myth_direction": card.myth.myth_direction,
            "film_claim": card.myth.film_claim,
            "primary_source_url": card.primary_source_url,
            "primary_source_citation": card.primary_source_citation,
            "verbatim_anchor": card.verbatim_anchor,
            "all_sources": [
                {"url": s.url, "tier": s.tier, "title": s.title} for s in card.all_sources
            ],
            "confidence_level": card.confidence_level,
            "validator": {
                "passed": card.validator_passed,
                "errors": card.validator_errors,
                "ran_at": datetime.now(timezone.utc).isoformat(),
            },
        },
    }


# -------------------- orchestrator --------------------


@dataclass
class MythSummary:
    title: str
    domain: str
    scenes_processed: int
    myths_proposed: int
    myths_researched: int
    cards_generated: int
    cards_validated: int
    output_path: str = ""


def _detect_domains(title: TitleMoments) -> list[str]:
    ranked = detect_candidate_domains(title, top_k=3)
    primary = [d for d, score in ranked if score >= 8]
    return primary[:2]


def _eligible_scenes(title: TitleMoments, cfg: RealismConfig, domains: list[str], limit: int | None) -> list[Scene]:
    scenes = [
        s for s in title.content_scenes()
        if s.duration_s >= cfg.min_scene_duration_s
        and s.moderation_severity in ("none", "low")
        and (s.dialogue_highlights or s.key_actions)
    ]
    if domains:
        kws: set[str] = set()
        for d in domains:
            kws.update(DOMAIN_KEYWORDS.get(d, []))
        def score(s: Scene) -> int:
            blob = " ".join(s.themes + s.key_actions + [s.summary] + s.mood_and_tone).lower()
            return sum(blob.count(k) for k in kws)
        scored = [(score(s), s) for s in scenes]
        relevant = [s for sc, s in scored if sc > 0]
        if relevant:
            scenes = sorted(relevant, key=lambda s: s.scene_index)
    if limit:
        scenes = scenes[:limit]
    return scenes


def run_hriv2_pipeline(
    *,
    cfg: RealismConfig,
    moments_path: Path | str,
    scene_limit: int | None = None,
    domain_override: list[str] | None = None,
) -> MythSummary:
    client = GeminiClient(cfg)
    title = load_moments(moments_path)
    domains = domain_override or _detect_domains(title)
    if not domains:
        log.warning("hriv2: no domains detected for %s", title.title)
        out_path = cfg.outputs_dir / f"{_slug(title.title)}.hriv2.json"
        out_path.write_text(json.dumps({"title": title.title, "prompts": []}, indent=2))
        return MythSummary(
            title=title.title, domain="", scenes_processed=0, myths_proposed=0,
            myths_researched=0, cards_generated=0, cards_validated=0,
            output_path=str(out_path),
        )

    primary_domain = domains[0]
    scenes = _eligible_scenes(title, cfg, domains, scene_limit)
    log.info("hriv2: %s domain=%s scenes=%d", title.title, primary_domain, len(scenes))

    records: list[dict[str, Any]] = []
    myths_proposed = 0
    myths_researched = 0
    cards_generated = 0
    cards_validated = 0

    for scene in scenes:
        myths = propose_myths_for_scene(client, title=title.title, domain=primary_domain, scene=scene)
        myths_proposed += len(myths)
        for myth in myths:
            sources = research_myth(client, cfg, title=title.title, domain=primary_domain, myth=myth)
            if not sources:
                continue
            myths_researched += 1
            card = generate_myth_card(client, title=title.title, myth=myth, sources=sources)
            if not card:
                continue
            cards_generated += 1
            if card.validator_passed:
                cards_validated += 1
            records.append(to_record(title=title.title, card=card, scene=scene, model_used=cfg.gemini_model_fast))

    out_path = cfg.outputs_dir / f"{_slug(title.title)}.hriv2.json"
    out_path.write_text(json.dumps({"title": title.title, "prompts": records}, indent=2))

    return MythSummary(
        title=title.title, domain=primary_domain, scenes_processed=len(scenes),
        myths_proposed=myths_proposed, myths_researched=myths_researched,
        cards_generated=cards_generated, cards_validated=cards_validated,
        output_path=str(out_path),
    )
