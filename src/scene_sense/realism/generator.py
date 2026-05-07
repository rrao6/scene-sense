"""Stage 7-8: generate the user-facing realism prompt and run the anti-hallucination validator."""
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from .claims import BoundClaim
from .gemini_client import GeminiClient
from .moments import Scene

log = logging.getLogger(__name__)


REALISM_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "body": {"type": "string"},
        "drawer": {"type": "string"},
        "realism_assessment": {
            "type": "string",
            "enum": ["accurate", "mixed", "exaggerated", "inaccurate"],
        },
        "used_quote_ids": {"type": "array", "items": {"type": "string"}},
        "used_citation_ids": {"type": "array", "items": {"type": "string"}},
        "confidence_level": {"type": "string", "enum": ["high", "medium", "low"]},
        "verifiability": {
            "type": "string",
            "enum": ["easily_verifiable", "requires_expert_interpretation", "limited_public_sources"],
        },
    },
    "required": ["headline", "body", "drawer", "realism_assessment", "confidence_level", "verifiability"],
}


GENERATOR_SYSTEM = (
    "You generate TubiX SceneSense 'How Real Is It?' realism prompts for a specific scene in a film. "
    "Rules:\n"
    "- Use ONLY the bound sources and quotes listed below. Do not introduce outside facts.\n"
    "- If you quote, the quoted text in `drawer` must appear verbatim in one of the listed quotes.\n"
    "- Reference characters by CHARACTER NAME (e.g. 'Kevin Lomax'), never the actor's real name.\n"
    "- The DRAWER must reference what actually happens in THIS scene — refer to specific dialogue, "
    "actions, or objects from the scene. Do not write generic prose about the profession broadly.\n"
    "- `headline` <= 60 chars, scene-specific and intriguing.\n"
    "- `body` <= 140 chars, clear top-line verdict tied to what happens in the scene.\n"
    "- `drawer` <= 600 chars, anchors the expert quote to what the viewer just watched.\n"
    "- If grounding is generalized (no named expert), cite the primary statute/rule in the drawer.\n"
    "- Output JSON only."
)


def _build_generator_prompt(
    *,
    title: str,
    scene: Scene,
    bound: BoundClaim,
    grounding_type: str,
) -> str:
    lines: list[str] = [
        f"Film: {title}",
        f"Scene index: {scene.scene_index} ({scene.start_time}–{scene.end_time})",
        f"Scene summary: {scene.summary}",
        f"Characters in scene: {', '.join(scene.characters) if scene.characters else '(none detected)'}",
        f"Key actions: {'; '.join(scene.key_actions[:4]) if scene.key_actions else '(none)'}",
    ]
    if scene.dialogue_highlights:
        dh = [d for d in scene.dialogue_highlights if d][:3]
        if dh:
            lines.append(f"Dialogue: {' / '.join(repr(d) for d in dh)}")
    lines.extend([
        "",
        f"Claim to assess: {bound.claim.claim_text}",
        f"Grounding type: {grounding_type}",
        "",
        "BOUND QUOTES (use only these for verbatim quotes in drawer):",
    ])
    for i, b in enumerate(bound.bindings):
        expert = ", ".join(e.name for e in b.source.experts if e.name) or "unspecified"
        lines.append(f"[Q{i}] speaker={expert} role={b.source.experts[0].role if b.source.experts else ''}")
        lines.append(f'     text: "{b.quote.text}"')
        lines.append(f"     url: {b.source.url}")
    if not bound.bindings:
        lines.append("(no named-expert bound quotes)")
    lines.append("")
    lines.append("GENERALIZED SOURCES (use for primary-citation support when no named expert quote):")
    seen = set()
    for src in ([b.source for b in bound.bindings] + bound.generalized_sources_from_bank):
        for i, c in enumerate(src.primary_citations):
            key = (c.citation, c.url)
            if key in seen:
                continue
            seen.add(key)
            lines.append(f"[C{len(seen)-1}] {c.citation} | {c.url} | {c.relevance}")
    lines.append("")
    lines.append(
        "Produce JSON matching the schema: headline, body, drawer, realism_assessment, "
        "used_quote_ids (e.g. 'Q0'), used_citation_ids (e.g. 'C0'), confidence_level, verifiability."
    )
    return "\n".join(lines)


def generate_prompt(
    client: GeminiClient,
    *,
    title: str,
    scene: Scene,
    bound: BoundClaim,
) -> dict[str, Any] | None:
    grounding_type = bound.grounding_type()
    if grounding_type == "unsupported":
        return None
    prompt = _build_generator_prompt(
        title=title, scene=scene, bound=bound, grounding_type=grounding_type
    )
    resp = client.structured(
        namespace="realism_generate",
        prompt=prompt,
        response_schema=REALISM_SCHEMA,
        system_instruction=GENERATOR_SYSTEM,
        temperature=0.2,
        model=client.cfg.gemini_model_fast,
    )
    if not resp:
        return None
    resp["_grounding_type"] = grounding_type
    return resp


# -------------------- validator --------------------


def _find_quoted_spans(text: str) -> list[str]:
    # match straight + curly quotes
    spans = re.findall(r"[\"“]([^\"”]{6,})[\"”]", text or "")
    return [s.strip() for s in spans]


def _verbatim_match(candidate: str, pool: list[str]) -> bool:
    """Candidate quote span must be a substring of (or contain) one of the bound quote texts.

    We normalize whitespace + case + punctuation to catch curly-quote and spacing differences.
    Also accepts candidate being a substring of the NORMALIZED pool entry (handles fragments).
    """
    def norm(s: str) -> str:
        t = re.sub(r"\s+", " ", s.strip().lower())
        t = re.sub(r"[“”\"'`]", "", t)
        t = re.sub(r"[.,;:!?]+$", "", t)
        return t

    n = norm(candidate)
    if len(n) < 6:
        return True  # ignore tiny fragments (e.g. quoted single words)
    for p in pool:
        pn = norm(p)
        if not pn:
            continue
        if n in pn or pn in n:
            return True
    return False


BANNED_NAME_FORMS = re.compile(
    r"\b(keanu reeves|al pacino|charlize theron|reese witherspoon|tom hanks|matt damon|linda cardellini|jennifer coolidge)\b",
    re.IGNORECASE,
)


def validate_prompt(
    *,
    generated: dict[str, Any],
    bound: BoundClaim,
    scene: Scene,
) -> tuple[bool, list[str]]:
    errors: list[str] = []
    headline = generated.get("headline", "") or ""
    body = generated.get("body", "") or ""
    drawer = generated.get("drawer", "") or ""
    assessment = generated.get("realism_assessment")
    grounding_type = generated.get("_grounding_type")

    if assessment not in ("accurate", "mixed", "exaggerated", "inaccurate"):
        errors.append(f"bad_assessment: {assessment}")
    if not headline or len(headline) > 80:
        errors.append("headline_length")
    if not body or len(body) > 200:
        errors.append("body_length")
    if not drawer or len(drawer) > 800:
        errors.append("drawer_length")

    # Quoted spans in drawer must appear verbatim in either (a) a bound expert quote or
    # (b) the scene's own dialogue_highlights (since those are VLM-grounded).
    drawer_spans = _find_quoted_spans(drawer)
    allowed_pool = [b.quote.text for b in bound.bindings] + list(scene.dialogue_highlights or [])
    for span in drawer_spans:
        if not _verbatim_match(span, allowed_pool):
            errors.append(f"drawer_quote_not_bound: {span[:60]}")

    # named_expert grounding requires at least one USED bound quote from a real named expert
    if grounding_type == "named_expert":
        from .source_bank import _looks_like_real_expert
        used_q_ids = set(generated.get("used_quote_ids") or [])
        has_named = False
        for i, b in enumerate(bound.bindings):
            if f"Q{i}" not in used_q_ids:
                continue
            if any(_looks_like_real_expert(e) for e in b.source.experts):
                has_named = True
                break
        if not has_named:
            errors.append("named_expert_no_used_real_expert_quote")

    # no actor names
    full_text = " ".join([headline, body, drawer])
    if BANNED_NAME_FORMS.search(full_text):
        errors.append("actor_name_in_prompt")

    # defamation safety-net: `inaccurate` assessment must not phrase as "lawyers/doctors do X"
    if assessment == "inaccurate":
        risky = re.search(r"\b(lawyers|doctors|attorneys|judges|professionals)\b\s+(really|actually|often|frequently)\s+(do|don't|will|won't)\b", full_text, re.IGNORECASE)
        if risky:
            errors.append("profession_generalization_risk")

    return (len(errors) == 0, errors)


# -------------------- emit --------------------


def emit_prompt_record(
    *,
    title: str,
    scene: Scene,
    bound: BoundClaim,
    generated: dict[str, Any],
    domain: str,
    model_used: str,
    validator_passed: bool,
    validator_errors: list[str],
) -> dict[str, Any]:
    """Render the final prompt-output JSON per docs/schema/prompt-output.md realism extension."""
    claim = bound.claim
    grounding_type = generated.get("_grounding_type", bound.grounding_type())

    # Emit expert attributions ONLY for experts whose quote was actually used in the drawer.
    from .source_bank import _looks_like_real_expert  # local import to avoid cycle at module load
    used_q_ids = set(generated.get("used_quote_ids") or [])
    direct_quotes_out: list[dict[str, Any]] = []
    expert_attributions: list[dict[str, Any]] = []
    seen_experts: set[tuple[str, str]] = set()
    for i, b in enumerate(bound.bindings):
        tag = f"Q{i}"
        used = tag in used_q_ids
        # attribute experts only for quotes the generator actually used
        if used:
            for e in b.source.experts:
                if not _looks_like_real_expert(e):
                    continue
                ek = (e.name, e.source_class)
                if ek in seen_experts:
                    continue
                seen_experts.add(ek)
                expert_attributions.append(
                    {
                        "name": e.name,
                        "source_class": e.source_class,
                        "role": e.role,
                        "firm_or_org": e.firm_or_org,
                        "verified_at": datetime.now(timezone.utc).date().isoformat(),
                    }
                )
        direct_quotes_out.append(
            {
                "text": b.quote.text,
                "speaker": b.quote.speaker,
                "source_url": b.source.url,
                "timestamp": b.quote.timestamp,
                "validation_hash": b.quote.validation_hash,
                "used_in_drawer": used,
                "relevance": b.relevance,
            }
        )

    generalized_sources_out: list[dict[str, Any]] = []
    for src in ([b.source for b in bound.bindings] + bound.generalized_sources_from_bank):
        for c in src.primary_citations:
            generalized_sources_out.append(
                {
                    "type": "primary_citation",
                    "citation": c.citation,
                    "url": c.url,
                    "relevance": c.relevance,
                }
            )

    prompt_id_seed = f"ss:{_slug(title)}:{scene.scene_index}:realism:{domain}:{_hash(claim.claim_text)}"

    record = {
        "title_id": f"tubi:{_slug(title)}",
        "title": title,
        "scene_index": scene.scene_index,
        "scene_start_time": scene.start_time,
        "scene_end_time": scene.end_time,
        "prompt_id": prompt_id_seed,
        "primitive": "how_real_is_it",
        "surface": ["ctv_pause"],
        "headline": generated.get("headline"),
        "body": generated.get("body"),
        "drawer": generated.get("drawer"),
        "options": None,
        "reveal": None,
        "follow_ups": [],
        "source_citations": [
            {
                "type": "expert_quote",
                "url": b.source.url,
                "anchor_text": (b.source.source_title or b.source.url),
                "confidence": "high" if b.source.is_named_expert_source() else "medium",
            }
            for b in bound.bindings
        ],
        "quality_scores": {},
        "hitl": {
            "state": "pending",
            "reviewer": None,
            "reviewed_at": None,
            "notes": None,
        },
        "monetization": {
            "eligible": grounding_type == "named_expert" and validator_passed,
            "advertiser_categories": [],
            "excluded_categories": [],
            "sponsorship_tier": "direct_sold",
        },
        "personalization_hints": {"archetypes": [], "cold_start_weight": 0.5},
        "generated_by": {
            "model": model_used,
            "prompt_version": "realism-v0.1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "realism": {
            "domain": domain,
            "assessment": generated.get("realism_assessment"),
            "claim_text": claim.claim_text,
            "scene_evidence": claim.scene_evidence,
            "expert_attribution": expert_attributions,
            "direct_quotes": direct_quotes_out,
            "generalized_sources": generalized_sources_out,
            "grounding_type": grounding_type,
            "verifiability": generated.get("verifiability"),
            "confidence_level": generated.get("confidence_level"),
            "validator": {
                "passed": validator_passed,
                "errors": validator_errors,
                "ran_at": datetime.now(timezone.utc).isoformat(),
            },
        },
    }
    return record


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")


def _hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:10]
