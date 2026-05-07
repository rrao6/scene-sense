# Eval strategy — open research

**Owner:** Rahul Rao; eng support from hackathon team (Aryan, Aidean, Aidan).

## Why
SceneSense generates LLM content surfaced in-player. Without a rigorous eval, HITL overhead explodes and trust erodes. We need a layered eval:

1. **Offline evals** before content reaches HITL (programmatic filters).
2. **HITL review** — ops approve/reject.
3. **Online evals** — tap/engagement/dwell once live, feeds back into ranker.

## Dimensions

| Dimension | Method | Who | Notes |
|---|---|---|---|
| Factual accuracy | Source-citation check + LLM judge + HITL spot audit | Pipeline + ops | Required for grounded primitives |
| Scene relevance | LLM judge against scene summary + key_objects + dialogue_highlights | Pipeline | Cheap, fast |
| Tone / brand fit | LLM judge with Tubi tone rubric | Pipeline | Need rubric doc |
| Safety / moderation | Moderation tag gating + classifier pass | Pipeline | Tight on mod-flagged scenes |
| Intrigue / "would I tap this?" | HITL panel + A/B in-prod | Ops + analytics | Hardest to automate |
| Redundancy | Embedding similarity across prompts in the same scene + adjacent | Pipeline | Avoid near-duplicates |
| Legal risk | Rules + HITL | Ops + legal | Competitive-brand adjacency check |

## Datasets
- **Gold set:** 3–5 titles × ~20 scenes each × N prompts per scene, each labeled approve/reject with reasons. Hand-curated. Lives in `data/eval/gold/`.
- **Silver set:** HITL output from early beta runs — used to train ranker.
- **Live telemetry:** tap/dwell/drawer-expand → eng layer → back into ranker training.

## Metrics
- Precision@K of ranked prompts (vs. HITL gold).
- HITL approval rate (% of generated prompts approved without edits).
- Post-launch: tap rate per impression, follow-up rate, send-to-phone conversion rate.

## Open questions
- LLM-as-judge reliability for intrigue — probably needs human calibration.
- How big a gold set do we need before we can trust offline metrics? (Target: 500–1000 prompts.)
- Reuse existing Tubi evals infra or build new?
