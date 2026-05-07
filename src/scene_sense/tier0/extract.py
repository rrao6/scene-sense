"""Turn OG Tubi Moments JSON fields into SceneSense prompt records, no LLM.

These prompts carry `generated_by.model = "tier0_rule_based"` and a validator
that only checks structural invariants. They are the most trustworthy prompts
we emit.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..realism.moments import Scene, TitleMoments, load_moments


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")


def _hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:10]


def _base_record(title: str, scene: Scene, primitive: str, seed: str) -> dict[str, Any]:
    return {
        "title_id": f"tubi:{_slug(title)}",
        "title": title,
        "scene_index": scene.scene_index,
        "scene_start_time": scene.start_time,
        "scene_end_time": scene.end_time,
        "prompt_id": f"ss:{_slug(title)}:{scene.scene_index}:{primitive}:{_hash(seed)}",
        "primitive": primitive,
        "surface": ["ctv_pause"],
        "hitl": {"state": "pending", "reviewer": None, "reviewed_at": None, "notes": None},
        "generated_by": {
            "model": "tier0_rule_based",
            "prompt_version": "tier0-v0.1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
    }


# ---------- 1. Wiki-matched trivia (scene_iq primitive) ----------


def extract_wiki_trivia_prompts(title_moments: TitleMoments, raw_scenes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Wikipedia-matched trivia are already grounded by the OG ingest. Emit as SceneIQ cards.

    Dedup each trivia fact to a single scene — the one with the highest match_confidence and
    (secondarily) the richest match_reasoning. OG pipeline over-matches facts to multiple scenes.
    """
    # Collect (fact_text, conf_rank, reasoning_len, scene_index, trivia_obj) — choose best per fact
    CONF_RANK = {"high": 2, "medium": 1}
    candidates: dict[str, tuple[int, int, int, dict[str, Any]]] = {}
    scenes_by_index = {s.scene_index: s for s in title_moments.scenes}
    for raw in raw_scenes:
        scene = scenes_by_index.get(raw.get("scene_index"))
        if not scene or scene.scene_type != "content":
            continue
        for t in raw.get("trivia") or []:
            conf = (t.get("match_confidence") or "").lower()
            if conf not in CONF_RANK:
                continue
            text = (t.get("text") or "").strip()
            if not text:
                continue
            key = text
            reasoning_len = len((t.get("match_reasoning") or ""))
            rank = CONF_RANK[conf]
            existing = candidates.get(key)
            if existing is None or (rank, reasoning_len) > (existing[0], existing[1]):
                candidates[key] = (rank, reasoning_len, scene.scene_index, t)

    out: list[dict[str, Any]] = []
    for text, (rank, _, scene_idx, t) in candidates.items():
        scene = scenes_by_index.get(scene_idx)
        if not scene:
            continue
        conf = (t.get("match_confidence") or "").lower()
        section = t.get("section", "")
        # Skip casting-heavy sections and any body that names actors outside the scene's cast.
        # These should flow through the `cast` primitive, not as a scene_iq fact.
        if _wiki_text_is_casting_about_actors_not_in_scene(text, scene, section):
            continue
        source_url = t.get("source_url") or ""
        record = _base_record(title_moments.title, scene, "scene_iq", text)
        record.update(
            {
                "headline": _headline_for_wiki(text, section),
                "body": _sentence_trim(text, 160),
                "drawer": text,
                "options": None,
                "reveal": None,
                "follow_ups": [],
                "source_citations": [
                    {
                        "type": "wikipedia",
                        "url": source_url,
                        "anchor_text": t.get("source_title") or "Wikipedia",
                        "confidence": conf,
                    }
                ],
                "quality_scores": {"relevance": 1.0 if conf == "high" else 0.7},
                "monetization": {
                    "eligible": conf == "high",
                    "advertiser_categories": [],
                    "excluded_categories": [],
                    "sponsorship_tier": "direct_sold",
                },
                "personalization_hints": {
                    "archetypes": [_archetype_for_section(section)],
                    "cold_start_weight": 0.7,
                },
                "tier0_meta": {
                    "source_field": "wikipedia_trivia",
                    "section": section,
                    "match_confidence": conf,
                    "match_reasoning": t.get("match_reasoning", ""),
                    "validator": {"passed": True, "errors": []},
                },
            }
        )
        out.append(record)
    # sort by scene then section, stable
    out.sort(key=lambda r: (r["scene_index"], r["headline"]))
    return out


def _wiki_text_is_casting_about_actors_not_in_scene(text: str, scene, section: str) -> bool:
    """Return True if this wiki body is casting-section prose about actors not detected in the scene.

    Prevents scene_iq cards like "Jennifer Coolidge was cast as Paulette..." from appearing
    on a scene where Jennifer Coolidge isn't detected. Those facts are legitimate but belong
    on scenes where the actor actually appears, via the cast primitive.
    """
    sec = (section or "").lower()
    if "cast" in sec:
        return True
    # Any casting-phrased wiki body is a cast primitive's job, not scene_iq.
    # Named-actor content belongs on the cast card, not a "scene fact."
    casting_patterns = [
        r"\bwas cast as\b",
        r"\bwere cast\b",
        r"\bcasting (?:of|for)\b",
        r"\bhad also been considered for\b",
        r"\boriginally wanted to play\b",
        r"\bSelma Blair was cast\b",  # example; the generic pattern above catches these
    ]
    import re
    low = text.lower()
    if any(re.search(p, low) for p in casting_patterns):
        return True
    return False


def _headline_for_wiki(text: str, section: str) -> str:
    """Short, viewer-facing hook derived from the fact text where possible.

    Falls back to section labels for factual categories we can't auto-phrase.
    """
    import re
    sec = (section or "").lower()
    # Pull a strong proper-noun or numeric anchor from the text if available
    t = text.strip().rstrip(".")
    # prefer "$X million" or numeric anchors
    money = re.search(r"\$\d[\d,\.]*\s?(?:million|billion|thousand|M|B|K)?", text)
    year = re.search(r"\b(19|20)\d{2}\b", text)
    # short hook patterns
    if "originally" in t.lower() or "original ending" in t.lower() or "was going to" in t.lower():
        return "The original version"
    if "cut" in t.lower() and ("from the film" in t.lower() or "did not make" in t.lower() or "unused" in t.lower()):
        return "Almost got cut"
    if "filmed at" in t.lower() or "shot at" in t.lower() or "location" in sec:
        return "Where it was filmed"
    if money:
        return "The real cost"
    if "change from the novel" in t.lower() or "from the book" in t.lower():
        return "Book vs. film"
    if "filming" in sec or "production" in sec:
        return "Behind the scenes"
    if "development" in sec or "screenplay" in sec or "writing" in sec:
        return "How it was written"
    if "music" in sec or "soundtrack" in sec:
        return "Music note"
    if "reception" in sec or "review" in sec:
        return "What critics said"
    if "release" in sec or "box office" in sec:
        return "When it came out"
    if year:
        return "Back in the day"
    return "Did you know?"


# keep old name as alias so callers don't break
_headline_for_section = _headline_for_wiki


def _archetype_for_section(section: str) -> str:
    sec = (section or "").lower()
    if "filming" in sec or "production" in sec:
        return "behind_the_scenes"
    if "cast" in sec:
        return "cast_career"
    if "music" in sec:
        return "music"
    if "reception" in sec:
        return "reception"
    return "production"


def _sentence_trim(text: str, max_chars: int) -> str:
    """Trim to max_chars, preferring a clean sentence/clause/word boundary.

    Tries: (1) cut at end of sentence; (2) cut at a comma/semicolon; (3) cut at word boundary.
    Never cuts mid-word. Adds ellipsis if we cut early.
    """
    t = text.strip()
    if len(t) <= max_chars:
        return t
    cut = t[:max_chars]
    # 1) sentence end
    last_period = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    if last_period >= int(max_chars * 0.5):
        return cut[: last_period + 1]
    # 2) clause break
    last_clause = max(cut.rfind(", "), cut.rfind("; "), cut.rfind(" — "))
    if last_clause >= int(max_chars * 0.6):
        return cut[: last_clause].rstrip() + "…"
    # 3) word boundary
    last_space = cut.rfind(" ")
    if last_space >= int(max_chars * 0.6):
        return cut[:last_space].rstrip() + "…"
    return cut.rstrip() + "…"


# ---------- 2. Songs (music trivia / sponsor hook) ----------


def extract_song_prompts(title_moments: TitleMoments, raw_scenes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    scenes_by_index = {s.scene_index: s for s in title_moments.scenes}
    emitted_songs: set[tuple[str, str]] = set()
    for raw in raw_scenes:
        songs = raw.get("songs") or []
        if not songs:
            continue
        scene = scenes_by_index.get(raw.get("scene_index"))
        if not scene or scene.scene_type != "content":
            continue
        for sg in songs:
            title_s = (sg.get("title") or "").strip()
            artist = (sg.get("artist") or "").strip()
            if not title_s or not artist:
                continue
            key = (title_s.lower(), artist.lower())
            if key in emitted_songs:
                continue
            emitted_songs.add(key)
            record = _base_record(title_moments.title, scene, "scene_iq", f"song:{title_s}:{artist}")
            record.update(
                {
                    "headline": "Music in this scene",
                    "body": f"“{title_s}” by {artist}",
                    "drawer": f"The song playing in this scene is “{title_s}” by {artist}, identified via audio recognition.",
                    "options": None,
                    "reveal": None,
                    "follow_ups": [],
                    "source_citations": [
                        {
                            "type": "audio_recognition",
                            "url": "",
                            "anchor_text": "Tubi audio recognition",
                            "confidence": "high",
                        }
                    ],
                    "quality_scores": {"relevance": 0.9},
                    "monetization": {
                        "eligible": True,
                        "advertiser_categories": ["streaming_music"],
                        "excluded_categories": [],
                        "sponsorship_tier": "direct_sold",
                    },
                    "personalization_hints": {"archetypes": ["music"], "cold_start_weight": 0.6},
                    "tier0_meta": {
                        "source_field": "songs",
                        "song_title": title_s,
                        "song_artist": artist,
                        "validator": {"passed": True, "errors": []},
                    },
                }
            )
            out.append(record)
    return out


# ---------- 3. Cast / "Recognize them?" (cast card primitive) ----------


# Skip well-known leads — their prompt is low-intrigue. Only flag recognizable
# faces beyond the top-billed. The generator decides based on celebrity frequency.
def extract_cast_prompts(title_moments: TitleMoments, raw_scenes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Count celeb frequency across the title so the lead is skipped per-scene.
    from collections import Counter

    freq: Counter[str] = Counter()
    for raw in raw_scenes:
        cd = (raw.get("content_desc") or {}).get("structured_data") or {}
        for c in (cd.get("celebrities") or []):
            freq[c] += 1
    if not freq:
        return []
    top_n = {name for name, _ in freq.most_common(3)}  # skip these — too obvious

    out: list[dict[str, Any]] = []
    seen_per_celeb: set[str] = set()
    scenes_by_index = {s.scene_index: s for s in title_moments.scenes}
    for raw in raw_scenes:
        scene = scenes_by_index.get(raw.get("scene_index"))
        if not scene or scene.scene_type != "content":
            continue
        cd = (raw.get("content_desc") or {}).get("structured_data") or {}
        for celeb in (cd.get("celebrities") or []):
            if celeb in top_n:
                continue
            if celeb in seen_per_celeb:
                continue
            # only emit once per celeb (first scene they appear in)
            seen_per_celeb.add(celeb)
            record = _base_record(title_moments.title, scene, "cast", f"cast:{celeb}")
            record.update(
                {
                    "headline": "Recognize them?",
                    "body": f"{celeb} appears in this scene.",
                    "drawer": f"{celeb} is in this scene. Learn more about their other roles.",
                    "options": None,
                    "reveal": None,
                    "follow_ups": [
                        {"headline": f"What else has {celeb} been in?", "prompt_id": ""},
                    ],
                    "source_citations": [
                        {
                            "type": "tubi_moments_face_rec",
                            "url": "",
                            "anchor_text": "Tubi face recognition",
                            "confidence": "medium",
                        }
                    ],
                    "quality_scores": {"relevance": 0.7, "intrigue": 0.7},
                    "monetization": {
                        "eligible": False,  # cast prompts need Tier-1 enrichment to be sellable
                        "advertiser_categories": [],
                        "excluded_categories": [],
                        "sponsorship_tier": "direct_sold",
                    },
                    "personalization_hints": {"archetypes": ["cast_career"], "cold_start_weight": 0.5},
                    "tier0_meta": {
                        "source_field": "celebrities",
                        "celeb_name": celeb,
                        "appearance_count": freq[celeb],
                        "validator": {"passed": True, "errors": []},
                    },
                }
            )
            out.append(record)
    return out


# ---------- orchestrator ----------


def extract_all_tier0(moments_path: Path | str) -> dict[str, Any]:
    title = load_moments(moments_path)
    import json as _json

    raw = _json.loads(Path(moments_path).read_text())
    raw_scenes = raw.get("scenes", [])

    wiki = extract_wiki_trivia_prompts(title, raw_scenes)
    songs = extract_song_prompts(title, raw_scenes)
    cast = extract_cast_prompts(title, raw_scenes)
    all_prompts = wiki + songs + cast
    return {
        "title": title.title,
        "counts": {
            "wiki_trivia": len(wiki),
            "songs": len(songs),
            "cast": len(cast),
            "total": len(all_prompts),
        },
        "prompts": all_prompts,
    }
