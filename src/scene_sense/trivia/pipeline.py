"""End-to-end trivia pipeline (grounded facts -> MCQ)."""
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
    _safe_parse_json,
    _slug,
)

log = logging.getLogger(__name__)


# -------------------- Step 1: topic proposals --------------------


TOPIC_SCHEMA = {
    "type": "object",
    "properties": {
        "topics": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "category": {
                        "type": "string",
                        "enum": [
                            "cast_career",
                            "production",
                            "behind_the_scenes",
                            "music",
                            "location",
                            "historical_reference",
                            "easter_egg",
                            "object_prop",
                            "cameo",
                        ],
                    },
                    "search_query": {"type": "string"},
                    "intrigue_score": {"type": "number"},
                },
                "required": ["topic", "category", "search_query"],
            },
        }
    },
    "required": ["topics"],
}

TOPIC_SYSTEM = (
    "You propose verifiable trivia TOPICS for a specific scene in a film. "
    "You do NOT answer the trivia yet — only propose topics that a Google search could verify. "
    "Rules:\n"
    "- Topics must be specific and testable (e.g. 'Linda Cardellini's TV roles after Legally Blonde' "
    "rather than 'Linda Cardellini is famous').\n"
    "- Each topic must include a concrete search_query a search engine could run.\n"
    "- Do not propose anything that depends on interpretation or opinion.\n"
    "- Prefer topics that tie tightly to what is visible or audible in the scene."
)


@dataclass
class TriviaTopic:
    topic: str
    category: str
    search_query: str
    intrigue_score: float = 0.5


def propose_topics(client: GeminiClient, *, title: str, scene: Scene) -> list[TriviaTopic]:
    prompt = (
        f"Film: {title}\n\n"
        f"Scene:\n{scene.as_llm_context()}\n\n"
        "Propose 2-4 trivia topics anchored to this specific scene. Each must include a "
        "search_query a reader could verify. Discard topics that are opinion or interpretation."
    )
    resp = client.structured(
        namespace="trivia_topics",
        prompt=prompt,
        response_schema=TOPIC_SCHEMA,
        system_instruction=TOPIC_SYSTEM,
        temperature=0.3,
    )
    out: list[TriviaTopic] = []
    for t in resp.get("topics", []):
        if not t.get("topic") or not t.get("search_query"):
            continue
        out.append(
            TriviaTopic(
                topic=t["topic"],
                category=t.get("category", "production"),
                search_query=t["search_query"],
                intrigue_score=float(t.get("intrigue_score") or 0.5),
            )
        )
    return out


# -------------------- Step 2: ground a topic via Google Search --------------------


@dataclass
class GroundedSource:
    url: str
    title: str
    source_type: str
    fetched_body: str = ""
    body_hash: str = ""

    def as_snippet(self, max_chars: int = 20000) -> str:
        return self.fetched_body[:max_chars]


def ground_topic(
    client: GeminiClient, cfg: RealismConfig, *, topic: TriviaTopic, title: str
) -> list[GroundedSource]:
    # Run two queries per topic to widen recall and set up corroboration.
    queries = [topic.search_query]
    # Add a title-bound variant of the same query to anchor back to the film.
    if title.lower() not in topic.search_query.lower():
        queries.append(f'"{title}" {topic.search_query}')

    seen: set[str] = set()
    sources: list[GroundedSource] = []
    for q in queries:
        prompt = (
            f"Run a Google search for: {q}\n"
            "After searching, describe the top 3-6 most authoritative results. "
            "Do NOT invent any URL. Only describe what the search returned."
        )
        grounded = client.grounded(
            namespace=f"trivia_ground_{_slug(topic.category)}",
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
            # Title-grounding: reject sources whose body doesn't mention the film.
            tokens = [t for t in re.split(r"\W+", title.lower()) if len(t) >= 4]
            hits = sum(1 for t in tokens if t in body.lower())
            if tokens and hits < max(1, len(tokens) // 2):
                continue
            sources.append(
                GroundedSource(
                    url=url,
                    title=cit.get("title") or url,
                    source_type=stype,
                    fetched_body=body,
                    body_hash=hashlib.sha256(body.encode("utf-8")).hexdigest()[:16],
                )
            )
    return sources


# -------------------- Step 3-4: fact extraction + MCQ generation --------------------


MCQ_SCHEMA = {
    "type": "object",
    "properties": {
        "fact_snippet": {"type": "string"},
        "snippet_source_index": {"type": "integer"},
        "headline": {"type": "string"},
        "question": {"type": "string"},
        "answer": {"type": "string"},
        "distractors": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 3,
            "maxItems": 3,
        },
        "reveal": {"type": "string"},
        "confidence_level": {"type": "string", "enum": ["high", "medium", "low"]},
        "usable": {"type": "boolean"},
        "reason_if_unusable": {"type": "string"},
    },
    "required": ["headline", "question", "answer", "distractors", "usable"],
}

MCQ_SYSTEM = (
    "You write a single multiple-choice trivia card for a CTV pause screen. A viewer has paused the "
    "movie and will see a headline + question + 4 options on their TV. Write for that audience.\n"
    "\n"
    "Copy rules (strict):\n"
    "- HEADLINE: ≤ 8 words, a curious hook phrased for a viewer (e.g. \"Bruiser's real name?\" not "
    "  \"The name of the dog actor who played Bruiser Woods\"). NO article-style description.\n"
    "  The first 2 words must carry the hook. Questions OK if short.\n"
    "- QUESTION: 8-20 words, conversational register. Include the scene reference so the viewer "
    "  knows why they're being asked. Avoid film-title stuffing (e.g. drop \"in the film X\" if the "
    "  viewer is literally watching it).\n"
    "- ANSWER: copied verbatim from fact_snippet. Short.\n"
    "- DISTRACTORS: 3 plausible but clearly wrong alternatives. Hard rules:\n"
    "    * Must be the same KIND of thing as the answer (actor name ↔ actor names, breed ↔ breeds).\n"
    "    * Comparable length to the answer (within 2x character count).\n"
    "    * Must NOT appear anywhere in the fact_snippet, not even as a substring.\n"
    "    * Must NOT be the character's own name or a word from the question.\n"
    "    * Must NOT rephrase the correct answer.\n"
    "- REVEAL: one natural sentence that teaches the viewer a new bit of context AFTER they answer. "
    "  Not a tautological restatement of the question.\n"
    "\n"
    "Source rules:\n"
    "- fact_snippet MUST appear verbatim in one of the provided SOURCES.\n"
    "- The answer MUST appear verbatim in fact_snippet.\n"
    "- If the sources don't support a clean fact, set usable=false with a reason. Never fabricate.\n"
    "- Prefer scene-grounded surprise over generic filmography trivia."
)


@dataclass
class TriviaPrompt:
    scene_index: int
    topic: TriviaTopic
    headline: str
    question: str
    answer: str
    distractors: list[str]
    reveal: str
    fact_snippet: str
    source_url: str
    source_title: str
    confidence_level: str
    validator_passed: bool
    validator_errors: list[str] = field(default_factory=list)


BLACKLIST_DOMAINS = {
    # User-generated / e-commerce / sketchy
    "poshmark.com", "ebay.com", "etsy.com", "pinterest.com",
    "mercari.com", "thredup.com", "depop.com",
    # Random wordpress / blogspot / free-host blogs
    "wordpress.com", "blogspot.com", "medium.com",
    # Wiki farms
    "fandom.com", "wikia.com", "alchetron.com",
    # Fact-aggregator SEO farms
    "facts.net", "kiddle.co", "grokipedia.com",
    "famousbirthdays.com", "celebsagewiki.com",
    # Forum / Q&A
    "answers.com", "quora.com", "yahoo.com",
}


def _domain_of(url: str) -> str:
    import urllib.parse
    try:
        host = (urllib.parse.urlparse(url).hostname or "").lower()
    except Exception:
        return ""
    parts = host.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def _is_low_credibility_source(url: str) -> bool:
    if not url:
        return True
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    root = _domain_of(url)
    if root in BLACKLIST_DOMAINS:
        return True
    if any(host == d or host.endswith("." + d) for d in BLACKLIST_DOMAINS):
        return True
    return False


def _check_option_kind(question: str, answer: str, distractors: list[str], category: str) -> str | None:
    """Sanity-check that options share a KIND with each other.

    Catches: question asks 'which film' but options are character names; question asks
    'who played her' but options include film titles; etc.
    """
    all_opts = [answer] + list(distractors)

    # Classification heuristics — each option gets a rough 'kind' bucket.
    def classify(opt: str) -> str:
        t = (opt or "").strip()
        if not t:
            return "empty"
        # film-title-ish: multiple capitalized tokens + common film-title patterns
        if re.search(r'\b(the|a|an)\b', t.lower()) and len(t.split()) >= 2:
            return "phrase"
        # Year-only
        if re.fullmatch(r"\d{4}", t):
            return "year"
        # Named-person: 2-3 Capitalized tokens w/ no lowercase connectors
        if re.fullmatch(r"[A-Z][A-Za-z'\.\-]+(?:\s+[A-Z][A-Za-z'\.\-]+){1,2}", t):
            return "person_or_place"
        # single capitalized word
        if re.fullmatch(r"[A-Z][a-z]+", t):
            return "single_word"
        return "other"

    kinds = [classify(o) for o in all_opts]
    # Broad categories merge: phrase+year+single_word+other are all "not person" roughly
    # What we really flag: when question explicitly asks "which film" / "what movie" but
    # at least one option is a bare character name or single word.
    q_lower = question.lower()
    asks_film = any(phrase in q_lower for phrase in ("which film", "which movie", "what film", "what movie", "in which animated film", "in what animated film", "in what 2001 film"))
    asks_who = any(phrase in q_lower for phrase in ("who played", "who plays", "who portrays", "who designed"))

    # Rule: if asks for a film, answer must be a phrase (multi-word)
    if asks_film and len(answer.split()) == 1:
        return "asks_film_but_answer_is_single_word"

    # Rule: all options should have similar length — flag if variance > 3x
    lens = [len(o) for o in all_opts]
    if lens and max(lens) / max(1, min(lens)) > 4:
        return f"option_length_variance({min(lens)}..{max(lens)})"

    # Rule: for cast_career, options should all look like person names
    if category in ("cast_career", "cameo") and asks_who:
        non_person = [o for o in all_opts if classify(o) != "person_or_place"]
        # Allow if ALL options are non-person (some questions ask about place/organization)
        if non_person and len(non_person) < len(all_opts):
            return f"mixed_option_kinds_in_cast_question({non_person[0][:30]})"

    return None


def _build_mcq_prompt(
    title: str, scene: Scene, topic: TriviaTopic, sources: list[GroundedSource],
    *, forbidden_distractors: list[str] | None = None, retry_note: str = "",
) -> str:
    lines: list[str] = [
        f"Film: {title}",
        f"Scene context:\n{scene.as_llm_context()}",
        f"Topic: {topic.topic} ({topic.category})",
        "",
        "SOURCES (use only these; copy your fact_snippet verbatim from one of them):",
    ]
    for i, s in enumerate(sources):
        lines.append(f"[S{i}] {s.source_type} | {s.title}\n    url: {s.url}\n    body: {s.as_snippet(10000)}")
    lines.append(
        "\nProduce a single MCQ with: fact_snippet (verbatim from a source), snippet_source_index, "
        "question, answer (verbatim from the fact_snippet), 3 plausible distractors, reveal, "
        "confidence_level, usable.\n"
        "Hard rules:\n"
        "- Every distractor must be clearly wrong. Do NOT use any phrase that appears in the fact_snippet.\n"
        "- Distractors must be comparable length to the answer (within 2x).\n"
        "- Headline stays under 60 chars; it is a 1-line topic title, NOT the topic description."
    )
    if forbidden_distractors:
        lines.append(
            "\nPREVIOUS ATTEMPT REJECTED. Do NOT reuse these distractor strings: "
            + ", ".join(f'"{d}"' for d in forbidden_distractors)
        )
    if retry_note:
        lines.append(f"\nNotes from validator: {retry_note}")
    return "\n".join(lines)


def generate_mcq(
    client: GeminiClient,
    *,
    title: str,
    scene: Scene,
    topic: TriviaTopic,
    sources: list[GroundedSource],
) -> TriviaPrompt | None:
    if not sources:
        return None

    # Up to 2 attempts: if distractors overlap the snippet, retry with the bad distractors banned.
    forbidden: list[str] = []
    last_retry_note = ""
    resp: dict[str, Any] = {}
    for attempt in range(2):
        prompt = _build_mcq_prompt(
            title, scene, topic, sources,
            forbidden_distractors=forbidden or None,
            retry_note=last_retry_note,
        )
        resp = client.structured(
            namespace=f"trivia_mcq_a{attempt}",
            prompt=prompt,
            response_schema=MCQ_SCHEMA,
            system_instruction=MCQ_SYSTEM,
            temperature=0.2 + 0.1 * attempt,
            model=client.cfg.gemini_model_fast,
        )
        if not resp or not resp.get("usable"):
            break
        snippet_preview = (resp.get("fact_snippet") or "").strip()
        distractors_preview = resp.get("distractors") or []
        overlapping = [d for d in distractors_preview if d and _best_substring_ratio(d, snippet_preview) > 0.9]
        if not overlapping:
            break
        forbidden.extend(overlapping)
        last_retry_note = f"distractor(s) overlapped snippet: {overlapping}. Regenerate with different distractors."
    if not resp.get("usable"):
        return None
    question = (resp.get("question") or "").strip()
    answer = (resp.get("answer") or "").strip()
    distractors = resp.get("distractors") or []
    reveal = (resp.get("reveal") or "").strip()
    snippet = (resp.get("fact_snippet") or "").strip()
    src_idx = resp.get("snippet_source_index")
    if not question or not answer or len(distractors) != 3:
        return None

    # Validator
    errors: list[str] = []
    if not isinstance(src_idx, int) or src_idx < 0 or src_idx >= len(sources):
        errors.append("bad_source_index")
        chosen_source = sources[0]
    else:
        chosen_source = sources[src_idx]
    # fact_snippet must appear in chosen_source body
    snippet_ratio = _best_substring_ratio(snippet, chosen_source.fetched_body) if snippet else 0.0
    if snippet_ratio < 0.85:
        errors.append(f"fact_snippet_not_in_source(ratio={snippet_ratio:.2f})")
    # answer must appear in fact_snippet
    answer_in_snippet = _best_substring_ratio(answer, snippet) if snippet else 0.0
    if answer_in_snippet < 0.85:
        errors.append(f"answer_not_in_snippet(ratio={answer_in_snippet:.2f})")
    # distractors should not literally appear in the snippet
    for d in distractors:
        if _best_substring_ratio(d, snippet) > 0.9:
            errors.append(f"distractor_matches_snippet: {d[:40]}")
    # scene grounding check: cast_career/cameo questions must reference a person from the scene.
    if topic.category in ("cast_career", "cameo"):
        scene_people = set()
        for p in (scene.characters or []):
            scene_people.update(p.lower().split())
        for p in (scene.detected_cast or []):
            scene_people.update(p.lower().split())
        q_tokens = set(re.findall(r"[A-Z][a-z]+", question))
        if q_tokens and not any(tok.lower() in scene_people for tok in q_tokens):
            if scene.detected_cast or scene.characters:
                errors.append("cast_trivia_person_not_in_scene")

    # Cross-source corroboration: for cast_career, require the answer to appear in >=2 sources.
    if topic.category == "cast_career" and answer:
        # count domains (not URLs) containing the answer text
        import urllib.parse
        domains_seen: set[str] = set()
        for src in sources:
            if _best_substring_ratio(answer, src.fetched_body) >= 0.7:
                try:
                    host = urllib.parse.urlparse(src.url).hostname or ""
                except Exception:
                    host = ""
                # collapse subdomains to root domain
                parts = host.split(".")
                root = ".".join(parts[-2:]) if len(parts) >= 2 else host
                if root:
                    domains_seen.add(root)
        if len(domains_seen) < 2:
            errors.append(f"cast_career_single_source(domains={len(domains_seen)})")

    # Source-quality blacklist: reject if the ONLY source is low-credibility.
    if _is_low_credibility_source(chosen_source.url):
        errors.append(f"low_credibility_sole_source({_domain_of(chosen_source.url)})")

    # MCQ option-kind validator: options must match question category.
    option_kind_error = _check_option_kind(question, answer, distractors, topic.category)
    if option_kind_error:
        errors.append(option_kind_error)
    # prevent actor real names leaking in — trivia about cast is OK as long as the scene refers to the character
    # (we trust the generator here; keep for a later iteration.)

    # Headline: take the generator's short hook; fall back to a synthesized short one if missing/too long.
    headline = (resp.get("headline") or "").strip()
    if not headline or len(headline) > 70:
        # synthesize: first ≤8 words of question, strip leading "What/Who/Where/According to X"
        q = re.sub(r"^(According to [^,]+,\s*|In the film[^,]+,\s*)", "", question, flags=re.IGNORECASE)
        q = re.sub(r"\s*\?$", "?", q)
        headline = " ".join(q.split()[:8]).rstrip(",.")

    return TriviaPrompt(
        scene_index=scene.scene_index,
        topic=topic,
        headline=headline,
        question=question,
        answer=answer,
        distractors=list(distractors),
        reveal=reveal,
        fact_snippet=snippet,
        source_url=chosen_source.url,
        source_title=chosen_source.title,
        confidence_level=resp.get("confidence_level", "medium"),
        validator_passed=len(errors) == 0,
        validator_errors=errors,
    )


# -------------------- emit record --------------------


def to_record(*, title: str, scene: Scene, tp: TriviaPrompt, model_used: str) -> dict[str, Any]:
    return {
        "title_id": f"tubi:{_slug(title)}",
        "title": title,
        "scene_index": scene.scene_index,
        "scene_start_time": scene.start_time,
        "scene_end_time": scene.end_time,
        "prompt_id": f"ss:{_slug(title)}:{scene.scene_index}:trivia:{hashlib.sha256(tp.question.encode()).hexdigest()[:10]}",
        "primitive": "trivia",
        "surface": ["ctv_pause"],
        "headline": tp.headline,
        "body": tp.question,
        "drawer": tp.reveal,
        "options": [
            {"id": "a", "label": tp.answer, "correct": True},
            *[
                {"id": chr(ord("b") + i), "label": d, "correct": False}
                for i, d in enumerate(tp.distractors)
            ],
        ],
        "reveal": tp.reveal,
        "follow_ups": [],
        "source_citations": [
            {
                "type": "web_article" if "youtube" not in tp.source_url else "youtube",
                "url": tp.source_url,
                "anchor_text": tp.source_title,
                "confidence": tp.confidence_level,
            }
        ],
        "quality_scores": {"intrigue": tp.topic.intrigue_score},
        "hitl": {"state": "pending", "reviewer": None, "reviewed_at": None, "notes": None},
        "monetization": {
            "eligible": tp.validator_passed,
            "advertiser_categories": [],
            "excluded_categories": [],
            "sponsorship_tier": "direct_sold",
        },
        "personalization_hints": {"archetypes": [tp.topic.category], "cold_start_weight": 0.5},
        "generated_by": {
            "model": model_used,
            "prompt_version": "trivia-v0.1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "trivia_meta": {
            "category": tp.topic.category,
            "fact_snippet": tp.fact_snippet,
            "source_url": tp.source_url,
            "validator": {
                "passed": tp.validator_passed,
                "errors": tp.validator_errors,
                "ran_at": datetime.now(timezone.utc).isoformat(),
            },
        },
    }


# -------------------- orchestrator --------------------


@dataclass
class TriviaSummary:
    title: str
    scenes_processed: int
    topics_proposed: int
    sources_grounded: int
    prompts_generated: int
    prompts_validated: int
    output_path: str = ""


def run_trivia_pipeline(
    *,
    cfg: RealismConfig,
    moments_path: Path | str,
    scene_limit: int | None = None,
) -> TriviaSummary:
    client = GeminiClient(cfg)
    title = load_moments(moments_path)
    scenes = [
        s
        for s in title.content_scenes()
        if s.duration_s >= cfg.min_scene_duration_s
        and s.moderation_severity in ("none", "low")
    ]
    if scene_limit:
        scenes = scenes[:scene_limit]
    log.info("trivia: processing %d scenes of %s", len(scenes), title.title)

    records: list[dict[str, Any]] = []
    topics_proposed = 0
    sources_grounded = 0
    prompts_generated = 0
    prompts_validated = 0

    for scene in scenes:
        topics = propose_topics(client, title=title.title, scene=scene)
        topics_proposed += len(topics)
        for topic in topics:
            sources = ground_topic(client, cfg, topic=topic, title=title.title)
            sources_grounded += len(sources)
            if not sources:
                continue
            tp = generate_mcq(client, title=title.title, scene=scene, topic=topic, sources=sources)
            if not tp:
                continue
            prompts_generated += 1
            if tp.validator_passed:
                prompts_validated += 1
            records.append(to_record(title=title.title, scene=scene, tp=tp, model_used=cfg.gemini_model_fast))

    out_path = cfg.outputs_dir / f"{_slug(title.title)}.trivia.json"
    out_path.write_text(json.dumps({"title": title.title, "prompts": records}, indent=2))

    return TriviaSummary(
        title=title.title,
        scenes_processed=len(scenes),
        topics_proposed=topics_proposed,
        sources_grounded=sources_grounded,
        prompts_generated=prompts_generated,
        prompts_validated=prompts_validated,
        output_path=str(out_path),
    )
