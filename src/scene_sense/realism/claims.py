"""Stage 5-6: extract testable claims from scenes and bind them to source bank quotes."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from .gemini_client import GeminiClient
from .moments import Scene
from .source_bank import DirectQuote, Source, TitleSourceBank

log = logging.getLogger(__name__)


CLAIM_SCHEMA = {
    "type": "object",
    "properties": {
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim_text": {"type": "string"},
                    "scene_evidence": {
                        "type": "object",
                        "properties": {
                            "dialogue_highlights": {"type": "array", "items": {"type": "string"}},
                            "key_actions": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                    "candidate_domain": {"type": "string"},
                    "testable": {"type": "boolean"},
                    "reason_if_not_testable": {"type": "string"},
                },
                "required": ["claim_text", "scene_evidence", "candidate_domain", "testable"],
            },
        }
    },
    "required": ["claims"],
}


BINDING_SCHEMA = {
    "type": "object",
    "properties": {
        "bindings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source_index": {"type": "integer"},
                    "quote_index": {"type": "integer"},
                    "relevance": {
                        "type": "string",
                        "enum": ["yes", "partial", "no"],
                    },
                    "why": {"type": "string"},
                },
                "required": ["source_index", "quote_index", "relevance"],
            },
        }
    },
    "required": ["bindings"],
}


@dataclass
class Claim:
    scene_index: int
    claim_text: str
    scene_evidence: dict[str, Any]
    candidate_domain: str

    def as_llm_context(self) -> str:
        ev = self.scene_evidence or {}
        lines = [f"Claim: {self.claim_text}", f"Domain: {self.candidate_domain}"]
        if ev.get("dialogue_highlights"):
            lines.append("Dialogue: " + " / ".join(f'"{d}"' for d in ev["dialogue_highlights"][:4]))
        if ev.get("key_actions"):
            lines.append("Actions: " + "; ".join(ev["key_actions"][:4]))
        return "\n".join(lines)


@dataclass
class BoundQuote:
    source: Source
    quote: DirectQuote
    relevance: str  # "yes" | "partial"
    why: str = ""


@dataclass
class BoundClaim:
    claim: Claim
    bindings: list[BoundQuote] = field(default_factory=list)
    generalized_sources_from_bank: list[Source] = field(default_factory=list)

    def has_named_expert_binding(self) -> bool:
        return any(b.source.is_named_expert_source() and b.quote.validated_in_page for b in self.bindings)

    def grounding_type(self) -> str:
        if self.has_named_expert_binding():
            return "named_expert"
        if self.generalized_sources_from_bank or any(s.primary_citations for s in [b.source for b in self.bindings]):
            return "generalized_source_supported"
        return "unsupported"


CLAIM_SYSTEM = (
    "You are the Claim Extraction Layer for the TubiX SceneSense realism pipeline. "
    "Given a scene from a film, extract the real-world claims the scene implies — things a domain "
    "expert could verify or debunk. Discard scenes that don't make testable real-world claims."
)


def extract_claims(
    client: GeminiClient,
    *,
    title: str,
    domain: str,
    scene: Scene,
) -> list[Claim]:
    prompt = (
        f"Film: {title}\nDomain: {domain}\n\n"
        f"Scene:\n{scene.as_llm_context()}\n\n"
        "Task: extract 0-3 TESTABLE real-world claims the scene makes about the given domain. "
        "A testable claim is a proposition that a practicing professional, academic, or reputable "
        "journalist could agree or disagree with based on real-world practice, law, or research. "
        "Ignore purely fictional plot beats. Keep claims concise and domain-specific. "
        "If no testable claim exists, return an empty claims array."
    )
    resp = client.structured(
        namespace="claim_extract",
        prompt=prompt,
        response_schema=CLAIM_SCHEMA,
        system_instruction=CLAIM_SYSTEM,
        temperature=0.1,
    )
    out: list[Claim] = []
    for c in resp.get("claims", []):
        if not c.get("testable", False):
            continue
        out.append(
            Claim(
                scene_index=scene.scene_index,
                claim_text=(c.get("claim_text") or "").strip(),
                scene_evidence=c.get("scene_evidence") or {},
                candidate_domain=c.get("candidate_domain", domain),
            )
        )
    return [c for c in out if c.claim_text]


BINDING_SYSTEM = (
    "You are the Claim-Source Binding Layer. "
    "Given a claim and a numbered list of source quotes, decide for each quote whether it "
    "specifically addresses the claim: 'yes' (directly speaks to it), 'partial' (adjacent/related), "
    "or 'no'. Do not invent matches — bias toward 'no' when in doubt."
)


def bind_claim_to_sources(
    client: GeminiClient,
    *,
    claim: Claim,
    bank: TitleSourceBank,
) -> BoundClaim:
    indexed: list[tuple[int, int, Source, DirectQuote]] = []
    for si, source in enumerate(bank.sources):
        for qi, quote in enumerate(source.direct_quotes):
            indexed.append((si, qi, source, quote))

    if not indexed:
        return BoundClaim(claim=claim, bindings=[])

    lines = [f"CLAIM: {claim.claim_text}", ""]
    for n, (si, qi, src, q) in enumerate(indexed):
        expert = src.experts[0].name if src.experts else "unspecified"
        lines.append(
            f"[{n}] source_index={si} quote_index={qi} | {src.source_type} | speaker={expert}"
        )
        lines.append(f'    quote: "{q.text[:400]}"')
        lines.append(f"    scene_reference: {q.scene_reference}")
        lines.append("")

    prompt = "\n".join(lines) + (
        "\nFor each [n] entry, decide relevance to the CLAIM. "
        "Return JSON with `bindings`: list of {source_index, quote_index, relevance, why}. "
        "Only include entries judged 'yes' or 'partial'."
    )

    resp = client.structured(
        namespace="claim_binding",
        prompt=prompt,
        response_schema=BINDING_SCHEMA,
        system_instruction=BINDING_SYSTEM,
        temperature=0.1,
    )

    bindings: list[BoundQuote] = []
    for b in resp.get("bindings", []):
        relevance = b.get("relevance")
        if relevance not in ("yes", "partial"):
            continue
        si, qi = b.get("source_index"), b.get("quote_index")
        if si is None or qi is None:
            continue
        if si >= len(bank.sources):
            continue
        src = bank.sources[si]
        if qi >= len(src.direct_quotes):
            continue
        q = src.direct_quotes[qi]
        if not q.validated_in_page:
            # demote: unvalidated quote -> treat source's primary citations as generalized support
            continue
        bindings.append(BoundQuote(source=src, quote=q, relevance=relevance, why=b.get("why", "")))

    generalized: list[Source] = []
    # If no named-expert quote was bound, fall back to generalized primary sources.
    if not any(b.source.is_named_expert_source() for b in bindings):
        for s in bank.sources:
            if s.primary_citations:
                generalized.append(s)

    # Curated-statute fallback: always look for relevant statutes on the claim's domain and
    # surface them as generalized sources. The generator only consumes these when no
    # named-expert quote is available.
    from .source_bank import PrimaryCitation, Source as _Source
    from .statutes import find_relevant_statutes
    statutes = find_relevant_statutes(claim.candidate_domain, claim.claim_text)
    if statutes:
        synthetic = _Source(
            source_title=f"Curated primary sources ({claim.candidate_domain})",
            url="",
            source_type="statute",
            primary_citations=[
                PrimaryCitation(citation=s.citation, url=s.url, relevance=s.summary)
                for s in statutes
            ],
        )
        generalized.append(synthetic)

    return BoundClaim(claim=claim, bindings=bindings, generalized_sources_from_bank=generalized)
