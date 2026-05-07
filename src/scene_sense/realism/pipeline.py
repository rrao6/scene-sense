"""End-to-end realism pipeline orchestration."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .claims import bind_claim_to_sources, extract_claims
from .config import RealismConfig
from .eligibility import detect_candidate_domains, is_eligible, refine_domains_with_llm
from .gemini_client import GeminiClient
from .generator import emit_prompt_record, generate_prompt, validate_prompt
from .moments import Scene, TitleMoments, load_moments
from .source_bank import TitleSourceBank, build_source_bank

log = logging.getLogger(__name__)


@dataclass
class RunSummary:
    title: str
    domains: list[str]
    total_content_scenes: int
    scenes_processed: int
    total_claims: int
    claims_bound: int
    prompts_generated: int
    prompts_validated: int
    per_domain_source_counts: dict[str, int] = field(default_factory=dict)
    output_path: str = ""


def _eligible_scenes_for_pipeline(
    title: TitleMoments,
    cfg: RealismConfig,
    limit: int | None,
    domains: list[str] | None = None,
) -> list[Scene]:
    from .eligibility import DOMAIN_KEYWORDS

    scenes = [
        s for s in title.content_scenes()
        if s.duration_s >= cfg.min_scene_duration_s
        and s.moderation_severity in ("none", "low")
        and (s.dialogue_highlights or s.key_actions)
    ]
    # Prefer scenes whose themes/actions mention a keyword from one of the target domains.
    if domains:
        kws: set[str] = set()
        for d in domains:
            kws.update(DOMAIN_KEYWORDS.get(d, []))
        def score(s: Scene) -> int:
            blob = " ".join(
                s.themes + s.key_actions + [s.summary] + s.mood_and_tone
            ).lower()
            return sum(blob.count(k) for k in kws)
        scored = [(score(s), s) for s in scenes]
        relevant = [s for sc, s in scored if sc > 0]
        if relevant:
            # keep relevant scenes in scene_index order
            scenes = sorted(relevant, key=lambda s: s.scene_index)
    if limit:
        scenes = scenes[:limit]
    return scenes


def run_pipeline(
    *,
    cfg: RealismConfig,
    moments_path: Path | str,
    scene_limit: int | None = None,
    domain_override: list[str] | None = None,
) -> RunSummary:
    client = GeminiClient(cfg)
    title = load_moments(moments_path)
    log.info("Loaded %s: %d scenes (%d content)", title.title, len(title.scenes), len(title.content_scenes()))

    if domain_override:
        domains = domain_override
    else:
        eligible, kw_domains = is_eligible(title)
        if not eligible:
            log.warning("Title %s is not eligible (no strong domain signal)", title.title)
            return RunSummary(
                title=title.title,
                domains=[],
                total_content_scenes=len(title.content_scenes()),
                scenes_processed=0,
                total_claims=0,
                claims_bound=0,
                prompts_generated=0,
                prompts_validated=0,
            )
        domains = refine_domains_with_llm(client, title, kw_domains)
    log.info("Domains for %s: %s", title.title, domains)

    banks: dict[str, TitleSourceBank] = {}
    for d in domains:
        log.info("Building source bank for domain=%s", d)
        banks[d] = build_source_bank(client, cfg, title=title.title, domain=d)

    scenes = _eligible_scenes_for_pipeline(title, cfg, scene_limit, domains)
    log.info("Processing %d scenes (limit=%s)", len(scenes), scene_limit)

    out_records: list[dict[str, Any]] = []
    total_claims = 0
    claims_bound = 0
    prompts_generated = 0
    prompts_validated = 0

    for scene in scenes:
        for domain, bank in banks.items():
            claims = extract_claims(client, title=title.title, domain=domain, scene=scene)
            if not claims:
                continue
            total_claims += len(claims)
            for claim in claims:
                bound = bind_claim_to_sources(client, claim=claim, bank=bank)
                if bound.grounding_type() == "unsupported":
                    continue
                claims_bound += 1
                generated = generate_prompt(client, title=title.title, scene=scene, bound=bound)
                if not generated:
                    continue
                prompts_generated += 1
                passed, errors = validate_prompt(generated=generated, bound=bound, scene=scene)
                if passed:
                    prompts_validated += 1
                record = emit_prompt_record(
                    title=title.title,
                    scene=scene,
                    bound=bound,
                    generated=generated,
                    domain=domain,
                    model_used=cfg.gemini_model_fast,
                    validator_passed=passed,
                    validator_errors=errors,
                )
                out_records.append(record)

    out_path = cfg.outputs_dir / f"{_slug(title.title)}.realism.json"
    out_path.write_text(
        json.dumps(
            {
                "title": title.title,
                "domains": domains,
                "source_banks": {d: b.to_json() for d, b in banks.items()},
                "prompts": out_records,
            },
            indent=2,
        )
    )

    return RunSummary(
        title=title.title,
        domains=domains,
        total_content_scenes=len(title.content_scenes()),
        scenes_processed=len(scenes),
        total_claims=total_claims,
        claims_bound=claims_bound,
        prompts_generated=prompts_generated,
        prompts_validated=prompts_validated,
        per_domain_source_counts={d: len(b.sources) for d, b in banks.items()},
        output_path=str(out_path),
    )


def _slug(text: str) -> str:
    import re as _re
    return _re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
