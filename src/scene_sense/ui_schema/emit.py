"""Convert internal prompt records into the client UI shapes."""
from __future__ import annotations

import re
from typing import Any


def _scene_cuepoint(p: dict[str, Any]) -> dict[str, Any]:
    """Client-facing scene reference. Returns a small dict the UI can key off.

    Normalizes time format to HH:MM:SS.mmm so the client doesn't have to handle
    both 'MM:SS.mmm' and 'HH:MM:SS.mmm' (VLM output is inconsistent).
    """
    return {
        "sceneIndex": p.get("scene_index"),
        "startTime": _normalize_time(p.get("scene_start_time")),
        "endTime": _normalize_time(p.get("scene_end_time")),
    }


def _normalize_time(t: str | None) -> str:
    """Return time as HH:MM:SS.mmm. Accepts 'MM:SS.mmm' (no hour) or full format."""
    if not t:
        return ""
    parts = t.split(":")
    if len(parts) == 2:
        # "MM:SS.mmm" — pad hour
        mm, ss = parts
        return f"00:{mm.zfill(2)}:{ss}"
    if len(parts) == 3:
        h, mm, ss = parts
        return f"{h.zfill(2)}:{mm.zfill(2)}:{ss}"
    return t


def _options_to_ui(options: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if not options:
        return []
    out: list[dict[str, Any]] = []
    for i, opt in enumerate(options):
        out.append({
            "id": i,
            "isCorrect": bool(opt.get("correct")),
            "triviaOptionText": opt.get("label", ""),
        })
    return out


def _answer_text(p: dict[str, Any]) -> str:
    """The single-sentence explanation/reveal shown after the user answers."""
    # `drawer` is set to the reveal for trivia primitives (see trivia.to_record)
    return (p.get("reveal") or p.get("drawer") or "").strip()


def _actor_name_from_cast_prompt(p: dict[str, Any]) -> str:
    """For cast primitive, the actor name is in the body: '<Name> appears in this scene.'"""
    # Prefer the Tier-0 metadata — it carries the canonical face-recognized name
    t0 = p.get("tier0_meta") or {}
    if t0.get("celeb_name"):
        return t0["celeb_name"]
    body = p.get("body") or ""
    m = re.match(r"\s*([A-Z][A-Za-z'\.\-]+(?:\s+[A-Z][A-Za-z'\.\-]+)+)\s+appears", body)
    if m:
        return m.group(1).strip()
    return ""


def _actor_name_from_trivia(p: dict[str, Any]) -> str | None:
    """Extract the actor name referenced in an actor-trivia prompt.

    Priority:
      1. Pattern "Name (Character)" in the question body — strongest signal
      2. "<Actor> ... played/portrayed <Character>" with the actor coming first
      3. Any proper 2+ token name not in a stoplist of film/location/character names
    """
    body = p.get("body") or ""
    drawer = p.get("drawer") or ""
    reveal = p.get("reveal") or ""
    headline = p.get("headline") or ""
    fields = [body, drawer, reveal, headline]

    # 1. "Alanna Ubach (Serena)" or "Matthew Davis (Warner Huntington III)"
    for text in fields:
        m = re.search(r"([A-Z][A-Za-z'\.\-]+(?:\s+[A-Z][A-Za-z'\.\-]+)+)\s*\(", text)
        if m:
            candidate = m.group(1).strip()
            if _looks_like_person_name(candidate):
                return candidate

    # 2. "Matthew Davis, who plays Warner" / "Alanna Ubach, who plays Serena"
    for text in fields:
        m = re.search(
            r"([A-Z][A-Za-z'\.\-]+(?:\s+[A-Z][A-Za-z'\.\-]+)+)\s*,\s*who\s+(?:plays|played|portrays|portrayed)",
            text,
        )
        if m:
            candidate = m.group(1).strip()
            if _looks_like_person_name(candidate):
                return candidate

    # 3. "Before playing Warner ... Matthew Davis appeared" — actor at the end
    for text in fields:
        m = re.search(
            r"(?:Before|After)[^.]*?(?:playing|portraying|starring)[^.]+?([A-Z][A-Za-z'\.\-]+(?:\s+[A-Z][A-Za-z'\.\-]+)+)(?=\s+(?:appeared|starred|played|also))",
            text,
        )
        if m:
            candidate = m.group(1).strip()
            if _looks_like_person_name(candidate):
                return candidate

    # 4. Fall-back: any 2-3 token capitalized run that isn't a stoplisted name.
    # Actor trivia tends to have the actor near the start of the body/drawer.
    for text in fields:
        for m in re.finditer(r"\b([A-Z][A-Za-z'\.\-]{1,}(?:\s+[A-Z][A-Za-z'\.\-]{1,}){1,2})\b", text):
            candidate = m.group(1).strip()
            if _looks_like_person_name(candidate):
                return candidate
    return None


_STOPLIST_PROPER_NAMES = {
    "legally blonde", "harvard law", "devil advocate", "delta nu", "gracie law",
    "warner huntington", "elle woods", "mr gettys", "kevin lomax", "lloyd gettys",
    "mary ann", "mama imelda", "lola boa", "liz allen", "queen tulip",
    "welcome dollhouse", "urban legends", "villa del", "sol oro",
    "rose city", "royce hall", "bel air", "los angeles", "new york",
    "harvard university", "bergen county", "alachua county",
    "united states", "law review", "law school",
}


def _looks_like_person_name(candidate: str) -> bool:
    """Basic check: 2-3 tokens, not in stoplist, doesn't include common non-name words."""
    if not candidate:
        return False
    low = candidate.lower().strip()
    if low in _STOPLIST_PROPER_NAMES:
        return False
    # Reject if any token in stoplist
    for stop in _STOPLIST_PROPER_NAMES:
        if stop in low:
            return False
    tokens = candidate.split()
    if len(tokens) < 2 or len(tokens) > 4:
        return False
    # Reject if the first token is a common sentence-opener (As, When, Before, After, etc.)
    sentence_openers = {
        "As", "When", "While", "Before", "After", "If", "Although",
        "Since", "Because", "During", "Unless", "Until",
    }
    if tokens[0] in sentence_openers:
        return False
    # Reject if any token has obvious non-name vibes
    non_name_words = {
        "The", "A", "An", "In", "At", "On", "For", "To", "Of", "By",
        "With", "From", "Harvard", "Law", "School", "University",
        "College", "Street", "Avenue", "Highway", "Blvd", "Road",
        "Hall", "Building", "Plaza", "Center", "House", "Club",
        "Show", "Film", "Movie", "Series", "Season", "Episode",
        "Award", "Production", "Department", "Company",
    }
    for t in tokens:
        if t in non_name_words:
            return False
    return True


def _character_from_scene(p: dict[str, Any], scene_context: dict | None) -> str | None:
    """Character the actor is playing in THIS scene, if we can guess RELIABLY.

    We only return a character name if the prompt text names both actor and character
    (e.g. "Alanna Ubach (Serena)"). Otherwise we return None — blindly using the
    scene's first character is wrong (Jessica Cauffiel plays Margot, not Elle).
    """
    body = p.get("body") or ""
    drawer = p.get("drawer") or ""
    full = f"{body} {drawer}"
    # Pattern: "Actor Name (Character)"
    m = re.search(r"\b[A-Z][A-Za-z'\.\-]+(?:\s+[A-Z][A-Za-z'\.\-]+)+\s*\(\s*([A-Z][A-Za-z'\.\-]+(?:\s+[A-Z][A-Za-z'\.\-]+)*)\s*\)", full)
    if m:
        return m.group(1).strip()
    # Pattern: "who plays X" / "who portrays X"
    m = re.search(r"who\s+(?:plays|played|portrays|portrayed)\s+([A-Z][A-Za-z'\.\-]+(?:\s+[A-Z][A-Za-z'\.\-]+)*)", full)
    if m:
        return m.group(1).strip()
    return None


# -------------------- shape builders --------------------


def build_actor_fact(p: dict[str, Any], scene_context: dict | None = None) -> dict[str, Any] | None:
    actor_name = _actor_name_from_cast_prompt(p)
    if not actor_name:
        return None
    character = _character_from_scene(p, scene_context)
    fact_text = (p.get("drawer") or p.get("body") or "").strip()
    # Suppress generic placeholder cast cards — they lack a real fact until Tier-1
    # enrichment happens. UI should not show "X appears in this scene. Learn more."
    if _is_placeholder_cast_text(actor_name, fact_text):
        return None
    return {
        "type": "actorFact",
        "sceneCuepoint": _scene_cuepoint(p),
        "actorImage": None,
        "actorName": actor_name,
        "character": character,
        "factText": fact_text,
    }


def _is_placeholder_cast_text(actor_name: str, fact_text: str) -> bool:
    """Tier-0 cast cards emit templated filler. Detect it so the UI doesn't see it."""
    low = fact_text.lower()
    placeholder_patterns = [
        f"{actor_name.lower()} is in this scene",
        "learn more about their other roles",
        f"{actor_name.lower()} appears in this scene",
    ]
    return any(p in low for p in placeholder_patterns)


def build_scene_fact(p: dict[str, Any]) -> dict[str, Any]:
    header = p.get("headline") or ""
    body = (p.get("body") or "").strip()
    drawer = (p.get("drawer") or "").strip()
    # Dedup: body is often a truncated prefix of drawer. Prefer drawer when it
    # strictly contains body; prefer body when it's identical. Only concat when
    # drawer adds genuinely new material.
    def _norm(s: str) -> str:
        return re.sub(r"\s+", " ", s).strip().lower()
    body_n = _norm(body)
    drawer_n = _norm(drawer)
    if not drawer:
        text = body
    elif not body:
        text = drawer
    elif body_n == drawer_n:
        text = drawer
    elif body_n in drawer_n:
        # drawer is the longer, complete version
        text = drawer
    elif drawer_n in body_n:
        text = body
    else:
        text = f"{body} {drawer}"
    card: dict[str, Any] = {
        "type": "sceneFact",
        "sceneCuepoint": _scene_cuepoint(p),
        "factHeader": header,
        "factText": text,
    }
    if p.get("follow_ups"):
        card["followUps"] = [fu.get("headline") for fu in p["follow_ups"] if fu.get("headline")]
    if p.get("source_citations"):
        # expose the first source URL to the UI for a "Learn More" link
        card["sourceUrl"] = (p["source_citations"] or [{}])[0].get("url", "")
    return card


def build_actor_trivia(p: dict[str, Any], scene_context: dict | None = None) -> dict[str, Any]:
    actor_name = _actor_name_from_trivia(p) or ""
    character = _character_from_scene(p, scene_context)
    return {
        "type": "actorTrivia",
        "sceneCuepoint": _scene_cuepoint(p),
        "actorImage": None,
        "actorName": actor_name,
        "character": character,
        "triviaText": (p.get("body") or "").strip(),
        "triviaOptions": _options_to_ui(p.get("options")),
        "answerText": _answer_text(p),
    }


def build_scene_trivia(p: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "sceneTrivia",
        "sceneCuepoint": _scene_cuepoint(p),
        "triviaText": (p.get("body") or "").strip(),
        "triviaOptions": _options_to_ui(p.get("options")),
        "answerText": _answer_text(p),
    }


# -------------------- router --------------------


def to_ui(p: dict[str, Any], scene_context: dict | None = None) -> dict[str, Any] | None:
    primitive = p.get("primitive")
    if primitive == "cast":
        card = build_actor_fact(p, scene_context)
        return card  # may be None if placeholder / no name
    if primitive == "scene_iq":
        return build_scene_fact(p)
    if primitive == "how_real_is_it":
        return build_scene_fact(p)
    if primitive == "facts":
        return build_scene_fact(p)
    if primitive == "trivia":
        category = (p.get("trivia_meta") or {}).get("category", "")
        if category in ("cast_career", "cameo"):
            return build_actor_trivia(p, scene_context)
        return build_scene_trivia(p)
    return None


def emit_ui_bundle(
    *,
    title: str,
    prompts: list[dict[str, Any]],
    scene_lookup: dict[int, dict] | None = None,
) -> dict[str, Any]:
    """Produce the full UI bundle. Prompts should already be finalized (approved + deduped)."""
    scene_lookup = scene_lookup or {}
    cards: list[dict[str, Any]] = []
    skipped: list[str] = []
    for p in prompts:
        scene_ctx = scene_lookup.get(p.get("scene_index"))
        card = to_ui(p, scene_context=scene_ctx)
        if card is None:
            skipped.append(p.get("prompt_id", ""))
            continue
        card["_promptId"] = p.get("prompt_id")  # internal, ignorable by UI
        cards.append(card)
    return {
        "title": title,
        "counts": {
            "total": len(cards),
            "by_type": _count_by(cards, "type"),
            "skipped": len(skipped),
        },
        "cards": cards,
    }


def _count_by(items: list[dict], key: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for it in items:
        v = it.get(key, "?")
        out[v] = out.get(v, 0) + 1
    return out
