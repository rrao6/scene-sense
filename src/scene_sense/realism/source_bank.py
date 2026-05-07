"""Stage 3-4: Build the Title Source Bank.

Two-pass flow to guarantee quote authenticity:

  Pass 1 (discovery):   Gemini + Google Search grounding returns candidate sources
                        (url + expert name + source_class) — NOT quotes.
  Pass 2 (extraction):  Fetch each URL (or YouTube transcript) and have Gemini
                        extract verbatim quotes + timestamps directly from the
                        fetched body. This means quotes are always grounded in
                        real page text we can validate.
  Pass 3 (validation):  String-match every extracted quote back against the
                        fetched body. Reject quotes that don't match.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import requests
from bs4 import BeautifulSoup

from .config import RealismConfig
from .gemini_client import GeminiClient

log = logging.getLogger(__name__)


# -------------------- data classes --------------------


@dataclass
class Expert:
    name: str
    source_class: str
    role: str = ""
    firm_or_org: str = ""


@dataclass
class DirectQuote:
    text: str
    speaker: str = ""
    timestamp: str = ""
    scene_reference: str = ""
    validation_hash: str = ""
    validated_in_page: bool = False
    match_ratio: float = 0.0


@dataclass
class PrimaryCitation:
    citation: str
    url: str = ""
    relevance: str = ""


@dataclass
class Source:
    source_title: str
    url: str
    source_type: str
    experts: list[Expert] = field(default_factory=list)
    direct_quotes: list[DirectQuote] = field(default_factory=list)
    primary_citations: list[PrimaryCitation] = field(default_factory=list)
    url_resolved: bool = False
    fetched_body_hash: str = ""
    fetched_body_excerpt: str = ""
    validation_errors: list[str] = field(default_factory=list)

    def is_named_expert_source(self) -> bool:
        return any(_looks_like_real_expert(e) for e in self.experts)

    def validated_quotes(self) -> list[DirectQuote]:
        return [q for q in self.direct_quotes if q.validated_in_page]


@dataclass
class TitleSourceBank:
    title: str
    domain: str
    built_at: str
    sources: list[Source]
    queries_run: list[str]
    grounding_citations: list[dict[str, Any]]

    def named_expert_sources(self) -> list[Source]:
        return [s for s in self.sources if s.is_named_expert_source() and s.validated_quotes()]

    def to_json(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "domain": self.domain,
            "built_at": self.built_at,
            "queries_run": self.queries_run,
            "grounding_citations": self.grounding_citations,
            "sources": [
                {
                    **{k: v for k, v in asdict(s).items() if k not in ("experts", "direct_quotes", "primary_citations")},
                    "experts": [asdict(e) for e in s.experts],
                    "direct_quotes": [asdict(q) for q in s.direct_quotes],
                    "primary_citations": [asdict(c) for c in s.primary_citations],
                }
                for s in self.sources
            ],
        }


def _looks_like_real_expert(e: "Expert") -> bool:
    """Require a plausible human name + a professional source class.

    Rejects YouTube handles ('AndrewPrice'), pseudonyms ('Unfrozen Caveman Law Writer'),
    and single-token usernames.
    """
    sc = (e.source_class or "").lower()
    if sc not in ("practicing_professional", "academic", "journalist"):
        return False
    name = (e.name or "").strip()
    if not name:
        return False
    lower = name.lower()
    blocked = {
        "unspecified",
        "unspecified expert",
        "unspecified experts",
        "unspecified legal scholars",
        "unknown",
        "anonymous",
        "author",
        "editor",
    }
    if lower in blocked:
        return False
    # Must contain at least 2 space-separated tokens, each starting with an uppercase letter
    # and only composed of alphabetic characters (allow hyphens and periods).
    tokens = [t for t in re.split(r"\s+", name) if t]
    if len(tokens) < 2:
        return False
    for t in tokens:
        if not re.match(r"^[A-Z][A-Za-z'.\-]{1,}$", t):
            return False
    # Reject obvious persona/pseudonym markers.
    persona_markers = ("caveman", "lawyer writer", "blogger", "handle", "anon")
    if any(m in lower for m in persona_markers):
        return False
    return True


# -------------------- text utilities --------------------


def _normalize(text: str) -> str:
    t = re.sub(r"\s+", " ", text or "").strip().lower()
    t = re.sub(r"[“”\"'`.,;:!?()\[\]…—–-]+", "", t)
    return t


def _best_substring_ratio(needle: str, haystack: str) -> float:
    n = _normalize(needle)
    h = _normalize(haystack)
    if not n or not h:
        return 0.0
    if n in h:
        return 1.0
    best = 0.0
    win = len(n)
    if win < 16:
        return SequenceMatcher(None, n, h[: min(len(h), win * 4)]).ratio()
    step = max(1, win // 4)
    for i in range(0, max(1, len(h) - win + 1), step):
        chunk = h[i : i + win + 20]
        r = SequenceMatcher(None, n, chunk).ratio()
        if r > best:
            best = r
            if best >= 0.99:
                return best
    return best


def _fetch_url_text(url: str, timeout_s: int) -> tuple[bool, str]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
        )
    }
    try:
        resp = requests.get(url, timeout=timeout_s, headers=headers, allow_redirects=True)
    except Exception as exc:  # noqa: BLE001
        return False, f"request_failed: {exc}"
    if resp.status_code >= 400:
        return False, f"http_{resp.status_code}"
    ct = (resp.headers.get("Content-Type") or "").lower()
    if "html" in ct or "text" in ct:
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)
        return True, text
    return True, resp.text


def _extract_youtube_video_id(url: str) -> str | None:
    try:
        u = urlparse(url)
    except Exception:
        return None
    host = (u.hostname or "").lower()
    if "youtu.be" in host:
        return u.path.lstrip("/") or None
    if "youtube.com" not in host:
        return None
    if u.path.startswith("/shorts/"):
        return u.path.split("/")[2]
    if u.path.startswith("/embed/"):
        return u.path.split("/")[2]
    qs = parse_qs(u.query or "")
    v = qs.get("v")
    if v:
        return v[0]
    return None


def _fetch_youtube_transcript(url: str) -> tuple[bool, str, list[dict[str, Any]]]:
    """Returns (ok, concatenated_text, segments[{text, start, duration}])."""
    vid = _extract_youtube_video_id(url)
    if not vid:
        return False, "not_a_video_url", []
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except Exception:  # noqa: BLE001
        return False, "transcript_api_missing", []
    try:
        api = YouTubeTranscriptApi()
        fetched = api.fetch(vid, languages=["en", "en-US", "en-GB"])
    except Exception as exc:  # noqa: BLE001
        return False, f"transcript_fetch_failed: {exc}", []
    # Each snippet may be a dict or a dataclass-like object with .text/.start/.duration
    segments: list[dict[str, Any]] = []
    for seg in fetched:
        if isinstance(seg, dict):
            segments.append({
                "text": seg.get("text", ""),
                "start": seg.get("start", 0.0),
                "duration": seg.get("duration", 0.0),
            })
        else:
            segments.append({
                "text": getattr(seg, "text", ""),
                "start": getattr(seg, "start", 0.0),
                "duration": getattr(seg, "duration", 0.0),
            })
    text = " ".join(seg["text"] for seg in segments)
    return True, text, segments


def _hms(seconds: float) -> str:
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def _attach_timestamps_from_segments(quote_text: str, segments: list[dict[str, Any]]) -> str:
    """Locate the quote's best window in the transcript and return a HH:MM:SS–HH:MM:SS range."""
    if not segments:
        return ""
    nq = _normalize(quote_text)
    if not nq:
        return ""
    window = 10
    best_ratio = 0.0
    best_start = None
    best_end = None
    for i in range(len(segments) - 1):
        j = min(i + window, len(segments))
        chunk = " ".join(segments[k]["text"] for k in range(i, j))
        r = _best_substring_ratio(nq, chunk)
        if r > best_ratio:
            best_ratio = r
            best_start = segments[i]["start"]
            best_end = segments[j - 1]["start"] + segments[j - 1].get("duration", 0)
            if r >= 0.99:
                break
    if best_ratio >= 0.75 and best_start is not None and best_end is not None:
        return f"{_hms(best_start)}–{_hms(best_end)}"
    return ""


# -------------------- Pass 1: candidate discovery (grounded) --------------------


DISCOVERY_SYSTEM = (
    "You run targeted Google searches for a film. Your output is used downstream to surface real URLs "
    "from the Google Search grounding tool; you do not need to emit URLs yourself. "
    "Describe why a result is relevant if one is cited."
)


def _discover_candidates(
    client: GeminiClient,
    *,
    title: str,
    domain: str,
) -> tuple[list[dict[str, Any]], list[str], list[dict[str, Any]]]:
    """Use Google Search grounding to surface REAL URLs. We never trust the LLM to emit URLs.

    Returns (candidate_source_dicts, queries_run, grounding_citations).
    """
    # Run several targeted queries to broaden the candidate set.
    # Domain-aware professional synonyms improve recall vs a generic "{domain} expert" query.
    domain_terms = {
        "legal": ["lawyer", "attorney", "judge", "law professor", "legal scholar"],
        "medical": ["doctor", "physician", "nurse", "medical professional"],
        "historical": ["historian", "history professor"],
        "military": ["veteran", "military historian"],
        "science": ["scientist", "physicist", "engineer"],
        "hacking": ["hacker", "security researcher", "cybersecurity expert"],
        "financial": ["economist", "financial analyst"],
    }.get(domain, [domain])
    queries: list[str] = [
        f'{title} {domain_terms[0]} reacts youtube',
        f'{title} film {domain} realism accuracy',
        f'{title} "how realistic" {domain}',
        f'{title} {domain_terms[0]} review analysis',
        f'{title} {domain} experts interview',
    ]
    # Extra per-domain query targeting law reviews / academic sources for legal/medical
    if domain == "legal":
        queries.append(f'{title} law review article ethics')
    elif domain == "medical":
        queries.append(f'{title} medical journal accuracy')
    query_bundles = queries

    all_citations: list[dict[str, Any]] = []
    all_queries: list[str] = []
    seen_urls: set[str] = set()

    for q in query_bundles:
        prompt = (
            f"Run a Google search for: {q}\n"
            "After the search, list the top relevant results you saw. "
            "Do NOT invent any URL; only describe what the search returned."
        )
        grounded = client.grounded(
            namespace=f"discover_grounded_{domain}",
            prompt=prompt,
            system_instruction=DISCOVERY_SYSTEM,
            temperature=0.1,
        )
        all_queries.extend(grounded.get("queries") or [])
        for cit in grounded.get("citations") or []:
            url = (cit.get("url") or "").strip()
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            all_citations.append(cit)

    # Google sometimes returns its own redirector URL for grounding chunks. Resolve these to
    # actual destinations so we can fetch content.
    resolved: list[dict[str, Any]] = []
    for cit in all_citations:
        url = cit.get("url") or ""
        final_url = _resolve_redirect(url)
        if not final_url:
            continue
        resolved.append({"url": final_url, "title": cit.get("title") or ""})

    # Classify each URL into a source_type. This is a cheap structured call over the URL+title only;
    # it does NOT generate any URL content.
    candidates: list[dict[str, Any]] = []
    for cit in resolved:
        url = cit["url"]
        source_type = _classify_url(url)
        # Skip junk domains early
        if source_type == "skip":
            continue
        candidates.append(
            {
                "source_title": cit["title"] or url,
                "url": url,
                "source_type": source_type,
                "experts": [],  # experts are filled in after we read the body (Pass 2)
            }
        )

    return candidates, all_queries, all_citations


def _resolve_redirect(url: str, timeout_s: int = 8) -> str:
    """Follow HEAD/GET redirects to get the final URL (Google often returns a redirector)."""
    if not url:
        return ""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
        )
    }
    try:
        resp = requests.head(url, headers=headers, allow_redirects=True, timeout=timeout_s)
        final = str(resp.url) if resp.url else url
        if resp.status_code < 400:
            return final
        # some servers 405 on HEAD; try GET
        resp = requests.get(url, headers=headers, allow_redirects=True, timeout=timeout_s, stream=True)
        final = str(resp.url) if resp.url else url
        resp.close()
        if resp.status_code < 400:
            return final
        return ""
    except Exception:  # noqa: BLE001
        return ""


def _classify_url(url: str) -> str:
    """Cheap rule-based URL classification into source_type. Returns 'skip' for junk domains."""
    u = url.lower()
    if any(h in u for h in ("youtube.com/watch", "youtu.be/", "youtube.com/shorts/")):
        return "youtube"
    if "podcasts.apple.com" in u or "spotify.com/episode" in u or "/podcast" in u:
        return "podcast"
    if "jstor.org" in u or "ssrn.com" in u or "scholarlycommons" in u or "lawreview" in u or "law-review" in u or ".edu/" in u:
        return "academic"
    if "en.wikipedia.org" in u or "pinterest." in u or "reddit.com" in u:
        return "skip"
    # reputable journalism
    if any(h in u for h in ("nytimes.com", "latimes.com", "theatlantic.com", "vulture.com", "wsj.com", "abajournal.com", "law.com")):
        return "article"
    return "article"


# -------------------- Pass 2: quote extraction from real page content --------------------


QUOTE_EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "experts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "source_class": {
                        "type": "string",
                        "enum": [
                            "practicing_professional",
                            "academic",
                            "journalist",
                            "unspecified",
                        ],
                    },
                    "role": {"type": "string"},
                    "firm_or_org": {"type": "string"},
                },
                "required": ["name", "source_class"],
            },
        },
        "quotes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "speaker": {"type": "string"},
                    "scene_reference": {"type": "string"},
                    "primary_citations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "citation": {"type": "string"},
                                "relevance": {"type": "string"},
                            },
                            "required": ["citation"],
                        },
                    },
                },
                "required": ["text"],
            },
        },
    },
    "required": ["quotes"],
}


QUOTE_EXTRACT_SYSTEM = (
    "You extract VERBATIM expert quotes from a single source document (article text or video transcript).\n"
    "Hard rules:\n"
    "- Every 'text' you return MUST appear verbatim in the provided BODY. Copy character-for-character.\n"
    "- Only return quotes where a named expert is discussing the specified film.\n"
    "- Also identify the expert(s) whose voice the body represents (from the body text, not from memory).\n"
    "- source_class rules: practicing_professional = lawyer/doctor/engineer currently working in the field; "
    "academic = professor/researcher/scholar; journalist = domain journalist/critic; unspecified = cannot tell from body.\n"
    "- If no expert is named in the body, return empty experts and quotes arrays.\n"
    "- Never invent an expert name or quote."
)


def _extract_quotes_from_body(
    client: GeminiClient,
    *,
    title: str,
    domain: str,
    source_title: str,
    body_excerpt: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Returns (experts[], quotes[]). Both come strictly from the BODY text."""
    if not body_excerpt.strip():
        return [], []
    max_chars = 40000
    body_excerpt = body_excerpt[:max_chars]
    prompt = (
        f"FILM: {title}\nDOMAIN: {domain}\nSOURCE: {source_title}\n\n"
        "BODY (fetched from the real source page or video transcript — use ONLY this text):\n\n"
        f"{body_excerpt}\n\n"
        "First, list the experts whose voice this body represents (experts[]). "
        "Second, return up to 4 verbatim quotes from those experts about the film's realism in the given domain (quotes[]). "
        "If the body does not contain expert commentary on this film, return empty arrays."
    )
    resp = client.structured(
        namespace="quote_extract_v3",
        prompt=prompt,
        response_schema=QUOTE_EXTRACT_SCHEMA,
        system_instruction=QUOTE_EXTRACT_SYSTEM,
        temperature=0.1,
        model=client.cfg.gemini_model_deep,
    )
    return (resp.get("experts", []) or []), (resp.get("quotes", []) or [])


# -------------------- main build --------------------


def build_source_bank(
    client: GeminiClient,
    cfg: RealismConfig,
    *,
    title: str,
    domain: str,
) -> TitleSourceBank:
    cache_path = cfg.source_bank_dir / f"{_slug(title)}__{domain}.json"
    if cfg.enable_cache and cache_path.exists():
        log.info("source_bank cache hit: %s", cache_path)
        return _load_bank_from_json(cache_path)

    # Pass 1
    candidates, queries, grounding = _discover_candidates(client, title=title, domain=domain)
    log.info("[%s/%s] discovery found %d candidates", title, domain, len(candidates))

    sources: list[Source] = []
    for c in candidates:
        url = (c.get("url") or "").strip()
        if not url or not url.startswith("http"):
            continue
        source_title = c.get("source_title", "") or url
        source_type = c.get("source_type", "article")
        experts = [
            Expert(
                name=e.get("name", ""),
                source_class=e.get("source_class", "unspecified"),
                role=e.get("role", ""),
                firm_or_org=e.get("firm_or_org", ""),
            )
            for e in (c.get("experts") or [])
        ]
        src = Source(
            source_title=source_title,
            url=url,
            source_type=source_type,
            experts=experts,
        )

        # Pass 2: fetch real body and extract quotes from it
        body_text = ""
        yt_segments: list[dict[str, Any]] = []
        if source_type == "youtube" or "youtube.com" in url or "youtu.be" in url:
            ok, yt_text_or_err, yt_segments = _fetch_youtube_transcript(url)
            if ok:
                src.url_resolved = True
                body_text = yt_text_or_err
            else:
                src.validation_errors.append(yt_text_or_err)
                # fall back to HTML (title/description)
                ok2, body_or_err = _fetch_url_text(url, cfg.http_timeout_s)
                if ok2:
                    src.url_resolved = True
                    body_text = body_or_err
                else:
                    src.validation_errors.append(body_or_err)
        else:
            ok, body_or_err = _fetch_url_text(url, cfg.http_timeout_s)
            if ok:
                src.url_resolved = True
                body_text = body_or_err
            else:
                src.validation_errors.append(body_or_err)

        # Title-grounding: reject sources whose body doesn't mention the film title.
        if src.url_resolved and body_text:
            # allow partial title match (e.g., "Devil's Advocate" vs "The Devils Advocate")
            title_tokens = [t for t in re.split(r"\W+", title.lower()) if len(t) >= 4]
            body_lower = body_text.lower()
            hits = sum(1 for t in title_tokens if t in body_lower)
            if title_tokens and hits < max(1, len(title_tokens) // 2):
                src.validation_errors.append(f"title_not_grounded(hits={hits}/{len(title_tokens)})")
                body_text = ""  # don't extract quotes from off-topic pages

        if src.url_resolved and body_text:
            src.fetched_body_hash = hashlib.sha256(body_text.encode("utf-8")).hexdigest()[:16]
            src.fetched_body_excerpt = body_text[:2000]
            experts_from_body, extracted = _extract_quotes_from_body(
                client,
                title=title,
                domain=domain,
                source_title=source_title,
                body_excerpt=body_text,
            )
            # Pass 2 experts (extracted from real body text) replace any speculative ones.
            for e in experts_from_body:
                nm = (e.get("name") or "").strip()
                if not nm:
                    continue
                src.experts.append(
                    Expert(
                        name=nm,
                        source_class=e.get("source_class", "unspecified"),
                        role=e.get("role", ""),
                        firm_or_org=e.get("firm_or_org", ""),
                    )
                )
            for q in extracted:
                text = (q.get("text") or "").strip()
                if not text:
                    continue
                ratio = _best_substring_ratio(text, body_text)
                quote = DirectQuote(
                    text=text,
                    speaker=q.get("speaker", ""),
                    scene_reference=q.get("scene_reference", ""),
                    validation_hash=hashlib.sha256(text.encode("utf-8")).hexdigest()[:16],
                    match_ratio=round(ratio, 3),
                    validated_in_page=ratio >= cfg.quote_validator_threshold,
                )
                if quote.validated_in_page and yt_segments:
                    quote.timestamp = _attach_timestamps_from_segments(text, yt_segments)
                if not quote.validated_in_page:
                    src.validation_errors.append(
                        f"quote_unverified(ratio={ratio:.2f}): {text[:80]}"
                    )
                src.direct_quotes.append(quote)
                # primary citations extracted alongside the quote
                for pc in q.get("primary_citations", []) or []:
                    citation = pc.get("citation", "")
                    if not citation:
                        continue
                    src.primary_citations.append(
                        PrimaryCitation(
                            citation=citation,
                            relevance=pc.get("relevance", ""),
                        )
                    )
        sources.append(src)

    bank = TitleSourceBank(
        title=title,
        domain=domain,
        built_at=datetime.now(timezone.utc).isoformat(),
        sources=sources,
        queries_run=queries,
        grounding_citations=grounding,
    )
    cache_path.write_text(json.dumps(bank.to_json(), indent=2))
    named = sum(1 for s in sources if s.is_named_expert_source())
    validated = sum(1 for s in sources if s.validated_quotes())
    log.info(
        "[%s/%s] source_bank: %d candidates | %d named-expert | %d with validated quotes -> %s",
        title, domain, len(sources), named, validated, cache_path,
    )
    return bank


# -------------------- helpers --------------------


def _safe_parse_json(text: str) -> dict[str, Any]:
    if not text:
        return {}
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", stripped)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                return {}
        return {}


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _load_bank_from_json(path: Path) -> TitleSourceBank:
    data = json.loads(path.read_text())
    sources: list[Source] = []
    for s in data.get("sources", []):
        src = Source(
            source_title=s.get("source_title", ""),
            url=s.get("url", ""),
            source_type=s.get("source_type", "article"),
            experts=[Expert(**e) for e in s.get("experts", [])],
            direct_quotes=[DirectQuote(**q) for q in s.get("direct_quotes", [])],
            primary_citations=[PrimaryCitation(**c) for c in s.get("primary_citations", [])],
            url_resolved=s.get("url_resolved", False),
            fetched_body_hash=s.get("fetched_body_hash", ""),
            fetched_body_excerpt=s.get("fetched_body_excerpt", ""),
            validation_errors=s.get("validation_errors", []),
        )
        sources.append(src)
    return TitleSourceBank(
        title=data.get("title", ""),
        domain=data.get("domain", ""),
        built_at=data.get("built_at", ""),
        sources=sources,
        queries_run=data.get("queries_run", []),
        grounding_citations=data.get("grounding_citations", []),
    )
