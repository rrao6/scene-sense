# scene-sense

Workspace for **SceneSense** (content-intelligence layer) and **TubiX** (user-facing CTV interaction + ad-format layer).

**Positioning:** SceneSense/TubiX is a **CTV-first extension of Interactive Pause** — scene-aware premium direct-sold ad formats *and* real in-player interaction value for viewers (SceneIQ facts, cast, trivia, polls, explainers). Mobile, web, proactive playback prompts, dual-screen handoff, and conversational AI are Phase 2+.

This repo is a spec + prototyping workspace — not the production client / ad codebase. Final implementation lands in Tubi product repos.

## What's in here

| Path | Purpose |
|---|---|
| `docs/vision/` | Vision narratives (TubiX exec summary, platform walkthroughs: SPR / Minority Report / Legally Blonde) |
| `docs/prds/` | PRD suite — master SceneSense PRD, Content Intelligence, Client Experience, Monetization, and the baseline Interactive Pause PRD |
| `docs/schema/` | Tubi Moments schema docs derived from the model output |
| `docs/use-cases/` | UX primitive catalog (trivia, polls, SceneIQ, cast, send-to-phone, shoulder content, ...) |
| `docs/meeting-notes/` | Captured meeting notes from planning + hackathon scoping |
| `docs/research/` | Open research threads: opportunity sizing, legal, UX primitives, evals |
| `src/scene_sense/` | Python pipeline scaffolding (config, Databricks client, moments loader, LLM enrichment) |
| `scripts/` | CLIs for running the pipeline end-to-end |
| `data/samples/` | Reference outputs from the current Tubi Moments model (e.g. `Legally_Blonde.json`) |
| `data/outputs/` | Generated enrichment outputs (gitignored) |
| `data/eval/` | Eval sets + HITL annotation outputs |

## Quickstart

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in values — or reuse the existing .env

# Sanity-check: load the sample moments file and print scene count
python scripts/inspect_moments.py data/samples/Legally_Blonde.json

# Run enrichment over sample scenes (stub — see docs/prds/content-intelligence.md)
python scripts/enrich_moments.py data/samples/Legally_Blonde.json \
    --out data/outputs/Legally_Blonde.enriched.json
```

## Conventions

- PRDs live in `docs/prds/` as markdown; link out from the top-level `docs/README.md`.
- Prompts are versioned under `src/scene_sense/prompts/` as plain `.md` or `.txt` with a frontmatter `version:` so changes are diff-able.
- Eval sets live in `data/eval/` and are committed; runs are gitignored.
- `.env` is never committed. Use `.env.example` as the template.

## Status

Early. Most files in `docs/` are scaffolds populated with the raw source material pasted from planning docs. Next passes will clean them up into production-quality specs.
