"""Title eligibility + domain classification."""
from __future__ import annotations

import logging
from collections import Counter

from .gemini_client import GeminiClient
from .moments import TitleMoments

log = logging.getLogger(__name__)

DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "legal": [
        "legal", "law", "lawyer", "attorney", "court", "trial", "jury",
        "testimony", "cross-examination", "verdict", "judge", "objection",
        "prosecutor", "defendant", "witness", "voir dire", "ethics",
    ],
    "medical": [
        "medical", "doctor", "hospital", "surgery", "diagnosis", "patient",
        "nurse", "emergency room", "medication", "treatment", "pharma",
    ],
    "historical": [
        "historical", "war", "battle", "soldier", "era", "period", "1940s",
        "1960s", "wwii", "world war", "vietnam", "civil rights",
    ],
    "military": [
        "military", "combat", "army", "marines", "navy", "soldier", "mission",
        "officer", "rank", "bootcamp",
    ],
    "science": [
        "science", "physics", "chemistry", "biology", "engineering",
        "astronomy", "experiment", "research",
    ],
    "hacking": [
        "hacking", "cybersecurity", "computer", "network", "encryption",
        "malware", "coding", "firewall",
    ],
    "religious": [
        "religion", "church", "faith", "scripture", "prayer", "sermon",
        "biblical", "christian", "catholic",
    ],
}


def detect_candidate_domains(title: TitleMoments, top_k: int = 3) -> list[tuple[str, int]]:
    """Count keyword hits across all content scenes. Returns (domain, score) pairs."""
    counts: Counter[str] = Counter()
    haystack_parts: list[str] = []
    for s in title.content_scenes():
        haystack_parts.extend(s.themes)
        haystack_parts.extend(s.key_actions)
        haystack_parts.append(s.summary)
        haystack_parts.extend(s.mood_and_tone)
    haystack = " \n ".join(haystack_parts).lower()
    for domain, keywords in DOMAIN_KEYWORDS.items():
        for kw in keywords:
            if kw in haystack:
                counts[domain] += haystack.count(kw)
    ranked = counts.most_common(top_k)
    return ranked


def is_eligible(title: TitleMoments, min_keyword_score: int = 8) -> tuple[bool, list[str]]:
    """Title is eligible if a domain clears the keyword threshold."""
    ranked = detect_candidate_domains(title, top_k=3)
    if not ranked:
        return False, []
    primary = [d for d, score in ranked if score >= min_keyword_score]
    return bool(primary), primary


DOMAIN_REFINEMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "primary_domains": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": [
                    "legal", "medical", "historical", "military", "science",
                    "hacking", "book_accuracy", "stunt_physical", "religious",
                    "financial", "other",
                ],
            },
        },
        "reasoning": {"type": "string"},
    },
    "required": ["primary_domains"],
}


def refine_domains_with_llm(
    client: GeminiClient, title: TitleMoments, candidate_domains: list[str]
) -> list[str]:
    """LLM confirms/expands the keyword-detected domains. Falls back to keywords on failure."""
    if not candidate_domains:
        return []
    sample_scenes = title.content_scenes()[:6]
    scene_blob = "\n\n".join(s.as_llm_context() for s in sample_scenes)
    prompt = (
        f"Title: {title.title}\n"
        f"Candidate domains from keyword scan: {candidate_domains}\n\n"
        f"Sample scenes:\n{scene_blob}\n\n"
        "Identify the 1-3 primary real-world domains a viewer would most want "
        "expert 'How real is it?' commentary on. Use only domains supported by "
        "scene evidence. Return JSON."
    )
    try:
        resp = client.structured(
            namespace="domain_refine",
            prompt=prompt,
            response_schema=DOMAIN_REFINEMENT_SCHEMA,
            temperature=0.1,
        )
        result = resp.get("primary_domains") or candidate_domains
        return [d for d in result if d][:3]
    except Exception as exc:  # noqa: BLE001
        log.warning("Domain refinement failed, falling back to keywords: %s", exc)
        return candidate_domains[:3]
