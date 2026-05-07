# Generators runbook — Realism + Trivia pipelines

**Status:** v0.1, smoke-tested on *Devil's Advocate* (legal) and *Legally Blonde* (legal, cast-heavy).
**Owner:** Rahul Rao / hackathon team.

## What these pipelines do

Two independent primitive generators that turn Tubi Moments VLM JSON into SceneSense prompts with hard accuracy gates:

| Primitive | Source of truth | MVP validator |
|---|---|---|
| `how_real_is_it` | Named expert quotes extracted from real article bodies / YouTube transcripts | Every drawer quote must substring-match a bound quote; named-expert grounding requires a real-looking name in an *actually used* source |
| `trivia` | Web-grounded facts extracted verbatim from fetched page bodies | Answer must be verbatim in fact_snippet; fact_snippet must be verbatim in the chosen source body; cast-trivia must reference someone in the scene |

Both share the same accuracy posture: **never trust the LLM to emit URLs or invent quotes**. URLs come only from Gemini's Google Search grounding citations; quotes are extracted from the bodies we actually fetched.

## Setup

```bash
cd ~/scene-sense
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# .env must have GEMINI_API_KEY set
```

## Running

```bash
# Realism on Devil's Advocate (default: auto-detect domains; caches enabled)
python scripts/generate_realism.py data/samples/The_Devils_Advocate.json --limit 4

# Force specific domains
python scripts/generate_realism.py data/samples/The_Devils_Advocate.json --domain legal --limit 4

# Trivia
python scripts/generate_trivia.py data/samples/The_Devils_Advocate.json --limit 4
```

Outputs land in:
- `data/outputs/<title>.realism.json`
- `data/outputs/<title>.trivia.json`
- `data/outputs/source_banks/<title>__<domain>.json` — the per-title expert corpus (reusable)

Caches live in `.cache/realism/`. Delete to re-run from scratch:

```bash
rm -rf .cache/realism data/outputs
```

## Pipeline internals

### Realism — 10 stages (see `use-cases/how-real-is-it.md` for full spec)

1. **Load** VLM JSON → `Scene` objects with `themes_and_concepts`, `key_actions`, `dialogue_highlights`, `detected_cast`, `moderation_tags`.
2. **Eligibility gate** — keyword scan across scenes; requires ≥8 domain keyword hits.
3. **Domain classifier** — LLM confirms/refines keyword-detected domains.
4. **Source discovery (Pass 1)** — Gemini runs 4 targeted Google queries per domain; we keep **only URLs returned by Google Search grounding citations**, never LLM-emitted URLs.
5. **Fetch** — follow redirects, scrape article body via BeautifulSoup, or fetch YouTube transcript via `youtube-transcript-api` (which now requires `YouTubeTranscriptApi().fetch(vid)`).
6. **Quote extraction (Pass 2)** — Gemini reads the fetched body and returns verbatim quotes + the expert's name + source class, all from the body text only.
7. **Quote validation** — each extracted quote is substring-matched against the fetched body (threshold 0.88). Unmatched quotes are dropped.
8. **Expert gate** — `_looks_like_real_expert` requires 2+ capitalized human-name tokens + a professional source class. Handles like "AndrewPrice" and pseudonyms like "Unfrozen Caveman Law Writer" are rejected.
9. **Claim extraction** — per scene, LLM extracts 0–3 testable real-world claims.
10. **Claim↔source binding** — LLM judges each (claim, validated_quote) pair as yes/partial/no; only `yes`/`partial` retained.
11. **Analysis & structuring** — LLM generates headline/body/drawer using ONLY the bound quotes. Drawer quoted spans must substring-match one of the bound quote texts.
12. **Anti-hallucination validator** — enforces: quoted spans match bound quotes; grounding_type=named_expert requires an actually *used* quote from a real-looking expert; no actor real-names; profession-generalization guard against defamation risk.
13. **Emit** — writes records in the `prompt-output.md` realism extension schema; HITL state = `pending`.

### Trivia — 5 stages

1. **Load** VLM JSON.
2. **Topic proposal** — per scene, LLM emits 2–4 testable trivia topics + a `search_query` per topic.
3. **Ground via Google Search** — Gemini grounded call + resolve redirects + fetch bodies.
4. **MCQ generation** — LLM returns `fact_snippet` (verbatim from a source), question, answer (verbatim from fact_snippet), 3 distractors, reveal.
5. **Validator** — fact_snippet must be in source body; answer must be in fact_snippet; no distractor overlaps with snippet; cast trivia must reference someone in the scene's characters/detected_cast.

## Known accuracy gotchas

| Gotcha | Status |
|---|---|
| LLM fabricating YouTube URLs from memory | Fixed — URLs only come from Google Search grounding citations |
| YouTube transcript API 0.6 → 1.0 API change (`get_transcript` → `fetch`) | Fixed |
| LLM hallucinating expert names (pseudonyms / channel handles) | Caught at validator (`_looks_like_real_expert`) + emit-time expert-attribution leak fixed |
| Cast trivia about people not in the scene | Fixed — scene-grounding check against `characters` + `detected_cast` |
| Single-source factual errors (e.g. "Connie Nielsen plays Barbara") | Fixed — `cast_career` answers must appear in ≥2 independent domains |
| Off-topic sources (generic actor pages not about this film) | Fixed — title-grounding check requires ≥50% of title tokens in source body |
| Narrow search / missed experts | Fixed — 5–6 domain-tuned queries per domain, including law-review and professional synonyms |
| Primary statute fallback (FRE 611, ABA Model Rules) | Fixed — curated statute set in `realism/statutes.py`, auto-matched by claim tags, surfaced as `generalized_source_supported` |
| Generic/abstract realism drawer text | Fixed — generator receives scene dialogue + actions + character names and is required to anchor the drawer to what actually happens in the scene |
| LB source bank not returning legal sources because early scenes aren't legal | Fixed — pipeline pre-filters scenes by domain keywords before processing |

## Run metrics (as of 2026-05-07 on Devil's Advocate, 4 scenes)

- Realism: 10 claims extracted, 5 bound, 5 generated, **2 validator-passed** (3 rejected for pseudonym-expert use — working as intended).
- Trivia: 13 topics, 36 grounded sources, 10 generated MCQs, **7 validator-passed**.
- Gemini cost rough order: 4 scenes ≈ 60 model calls ≈ $1–2 at current Gemini 2.5 pricing (caching on).
- Wall-clock: ~5 min for realism + ~5 min for trivia on a 4-scene run.

## Scaling notes

- Full DA run (66 content scenes × 2 domains × ~8 LLM calls/scene ≈ 1000 calls). Budget ~$10–20, ~1 hr wall-clock.
- Source bank is cached per (title, domain), so re-running realism on more scenes does NOT re-do discovery/fetch.
- Gemini 2.5-flash used for cheap per-scene steps; 2.5-pro reserved for Pass-2 quote extraction and grounded discovery.

## HITL gate

Every emitted prompt has `hitl.state = "pending"` and `monetization.eligible = validator_passed`. Nothing is launch-ready until ops reviews. The validator output is the signal for which prompts need editorial-only framing vs. sponsored eligibility.

## Full pipeline: generate → eval → finalize

```bash
# 1. Tier-0 (OG-JSON-first, no API calls)
python scripts/generate_tier0.py data/samples/The_Devils_Advocate.json

# 2. Trivia + Realism (grounded web search + curated statutes)
python scripts/generate_trivia.py  data/samples/The_Devils_Advocate.json --limit 6
python scripts/generate_realism.py data/samples/The_Devils_Advocate.json --limit 6

# 3. Consolidate into final (full) + review (HITL card) JSONs, with inline deterministic eval
python scripts/finalize.py --title "The Devils Advocate" \
  --moments data/samples/The_Devils_Advocate.json \
  --outputs data/outputs/the_devils_advocate.tier0.json \
  --outputs data/outputs/the_devils_advocate.trivia.json \
  --outputs data/outputs/the_devils_advocate.realism.json \
  --with-eval
```

Outputs:
- `data/outputs/<title>.final.json` — full-fidelity record including `_eval{}` per prompt
- `data/outputs/<title>.review.json` — tight HITL review cards, one per prompt

## Seven-dimension scorecard

Every prompt is scored on:

| Dimension | Weight | What it checks |
|---|---|---|
| **accuracy** | 0.25 | Deterministic re-fetch: URL resolves, title-grounded, quote/fact verbatim in live body |
| **legal_safety** | 0.20 | No actor real names in realism; no profession-generalization defamation phrasing; no sponsored chrome on moderation-flagged scenes |
| **prompt_quality** | 0.15 | References scene characters/actions; avoids hedge-word pile-up without citation; no merged pseudonym attributions |
| **response_quality** | 0.10 | Trivia only: 4 options, exactly 1 correct, distractors ≠ answer, length balance |
| **verbosity** | 0.10 | Headline ≤70 chars, body ≤180, drawer ≤700 |
| **user_interaction** | 0.10 | Required display fields for CTV remote rendering |
| **monetization_fit** | 0.10 | `eligible` flag consistent with grounding type; statute-only realism not marked sponsor-eligible |

**Verdict rule:** `accuracy` or `legal_safety` < 0.8 → `reject`; overall ≥ 0.80 → `approve`; else `needs_edit`.

