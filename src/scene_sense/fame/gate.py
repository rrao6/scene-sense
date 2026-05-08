"""Fame scoring + veto.

Approach:
  1. HEAD request to en.wikipedia.org/wiki/<Name> — cheap signal for "has its own page."
  2. If the page exists, fetch size + reference count as a stronger proxy.
  3. Cached on disk per subject, persistent across runs.
  4. Fallback: small Gemini call for edge cases.

Scoring:
  5 = A-list / household name (Reese Witherspoon, Jennifer Coolidge)
  4 = recognizable (Luke Wilson, Raquel Welch, Victor Garber)
  3 = moderately famous (Linda Cardellini, Holland Taylor, Ali Larter)
  2 = niche / indie famous (Lisa Arch, Jessica Cauffiel, Matthew Davis)
  1 = obscure / not culturally famous (Sophie de Rakoff, Arleen C)

Default veto threshold: >=3 required for cast_career, cameo, object_prop (brand/designer).
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

import requests

from ..realism.config import RealismConfig
from ..realism.gemini_client import GeminiClient

log = logging.getLogger(__name__)


FAME_CACHE_FILE = "fame_cache.json"


def _wiki_title(name: str) -> str:
    return name.strip().replace(" ", "_")


_UA = {
    "User-Agent": "SceneSenseFameGate/0.1 (https://example.local; contact: pipeline@example.local)"
}


def _wiki_probe(name: str, timeout_s: int = 8) -> dict[str, Any] | None:
    """Lightweight Wikipedia existence probe + article size."""
    # Use the REST API summary endpoint — lighter than HTML, returns 404 for non-existent pages.
    import urllib.parse
    title = urllib.parse.quote(_wiki_title(name), safe="")
    api_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
    try:
        api_resp = requests.get(api_url, timeout=timeout_s, headers=_UA, allow_redirects=True)
    except Exception as exc:  # noqa: BLE001
        log.debug("fame: wiki API failed for %s: %s", name, exc)
        return None
    if api_resp.status_code == 404:
        return None
    if api_resp.status_code >= 400:
        return None

    # Page exists — fetch the full HTML for size + ref count signals
    html_url = f"https://en.wikipedia.org/wiki/{_wiki_title(name)}"
    try:
        resp = requests.get(html_url, timeout=timeout_s, headers=_UA, allow_redirects=True)
    except Exception:
        return {"exists": True, "size": 0, "refs": 0, "url": html_url}
    if resp.status_code >= 400:
        return {"exists": True, "size": 0, "refs": 0, "url": html_url}
    body = resp.text
    size = len(body)
    # Modern Wikipedia uses class="reference" for inline ref links + <cite> for bibliography entries
    refs = len(re.findall(r'class="reference"', body))
    if refs == 0:
        refs = len(re.findall(r"<cite\b", body))
    return {"exists": True, "size": size, "refs": refs, "url": html_url}


def _score_from_wiki(probe: dict[str, Any] | None) -> int:
    """Translate Wikipedia signals into a 1-5 fame score.

    Calibrated against Lia's gold:
      Reese Witherspoon: 306 refs / 740KB → 5
      Jennifer Coolidge: 108 refs / 400KB → 5
      Raquel Welch: 264 refs / 450KB → 5
      Ali Larter: 133 refs / 316KB → 4
      Luke Wilson: 29 refs / 150KB → 3
      Holland Taylor: 28 refs / 187KB → 3
      Matthew Davis: 29 refs / 160KB → 3
      Lisa Arch: 2 refs / 95KB → should be 2 (reject)
      Jessica Cauffiel: 11 refs / 107KB → should be 2 (reject per Lia)
      Sophie de Rakoff: no page → 1
    """
    if not probe or not probe.get("exists"):
        return 1
    refs = probe.get("refs", 0)
    size = probe.get("size", 0)
    # Require BOTH signals: refs gates quality, size gates existence-depth.
    if refs >= 150 and size >= 300_000:
        return 5
    if refs >= 80 and size >= 200_000:
        return 4
    if refs >= 25 and size >= 120_000:
        return 3
    if refs >= 10 or size >= 60_000:
        return 2
    return 1


def _load_cache(cfg: RealismConfig) -> dict[str, Any]:
    path = cfg.cache_dir / FAME_CACHE_FILE
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def _save_cache(cfg: RealismConfig, cache: dict[str, Any]) -> None:
    path = cfg.cache_dir / FAME_CACHE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, indent=2))


def score_subject(
    name: str,
    cfg: RealismConfig,
    client: GeminiClient | None = None,
) -> dict[str, Any]:
    """Return {'score': 1-5, 'source': 'wiki'|'llm'|'cache', 'details': {...}}."""
    name = (name or "").strip()
    if not name or len(name) < 3:
        return {"score": 1, "source": "empty", "details": {}}

    cache = _load_cache(cfg)
    key = name.lower()
    if key in cache:
        return {**cache[key], "source": "cache"}

    probe = _wiki_probe(name)
    score = _score_from_wiki(probe)
    result = {"score": score, "source": "wiki", "details": probe or {}}
    cache[key] = result
    _save_cache(cfg, cache)
    return result


# -------------------- veto helpers --------------------


def extract_named_subjects(text: str) -> list[str]:
    """Pull likely person/brand/place names from a text string.

    Heuristic: runs of 2-4 Capitalized tokens separated by spaces (allowing
    apostrophes, periods, hyphens).
    """
    STOP = {"The", "A", "An", "In", "On", "At", "For", "To", "Of", "By", "With",
            "From", "Who", "What", "Which", "When", "Where", "How", "Why",
            "Legally", "Blonde", "Gladiator", "Devils", "Advocate",  # film titles in-context
            "Law", "School", "Harvard", "Stanford", "University", "College"}
    candidates = re.findall(r"\b([A-Z][A-Za-z'\.\-]+(?:\s+[A-Z][A-Za-z'\.\-]+){1,3})\b", text)
    out: list[str] = []
    seen: set[str] = set()
    for c in candidates:
        # Skip if first token is a stop-word
        tokens = c.split()
        if tokens[0] in STOP:
            continue
        # Skip if ALL tokens are stop-words
        if all(t in STOP for t in tokens):
            continue
        if c.lower() in seen:
            continue
        seen.add(c.lower())
        out.append(c)
    return out


def subject_passes_fame_gate(
    subjects: list[str],
    cfg: RealismConfig,
    client: GeminiClient | None = None,
    min_score: int = 3,
) -> tuple[bool, list[dict[str, Any]]]:
    """All named subjects must score >= min_score. Returns (pass, per-subject details)."""
    details: list[dict[str, Any]] = []
    if not subjects:
        return True, []  # nothing to check
    for subj in subjects:
        r = score_subject(subj, cfg, client=client)
        r["name"] = subj
        details.append(r)
    all_pass = all(d["score"] >= min_score for d in details)
    return all_pass, details
