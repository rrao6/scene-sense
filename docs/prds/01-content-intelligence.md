# Content Intelligence PRD

**Status:** Draft (scaffold)
**Owner:** Rahul Rao (PM); Aryan Gupta (eng, schema)
**Last updated:** 2026-05-07

> Platform that turns a title into a set of ranked, HITL-approved scene-level prompts the client can surface. Builds on Tubi Moments as raw input. **MVP consumer is the CTV pause surface** (primary); mobile/web/proactive/dual-screen are P2 consumers of the same prompt store.

## 1. What this system does

Per the 2026-04-30 UX working session:

> *Content intelligence will likely consist of several small models behind 1 orchestration layer.*

Main jobs to be done:

1. **Title and scene profiling** — Understand the content and generate structured attributes. Requires a feature schema for titles that aggregates:
   - Core title metadata
   - Structured content signals (derived from synopsis, scripts, subtitles, chaptering)
   - Use-case "potential" signals (hardest — e.g. what tells the model a title has heavy lore or character mapping?)
   - Public / social-media knowledge
2. **Use-case selection** — Given those attributes, decide which engagement opportunities apply per scene.
3. **Primitive mapping** — Map each use case to the right UI primitive/format (see `docs/use-cases/primitive-catalog.md`).
4. **Content generation** — Generate the actual prompts, polls, facts, quizzes.
5. **Ranking and filtering** — Score for relevance, intrigue, tone match, safety, and redundancy.
   - HITL evals → in-prod data collection → eventually ML automated ranking/evals.

Plus: a **CMS layer** for manual overrides, editorial promotion, and approve/deny workflow for content-ops.

## 2. Inputs

- **Tubi Moments** JSON (see `docs/schema/tubi-moments.md`, sample at `data/samples/Legally_Blonde.json`)
- **Databricks content metadata** (`DATABRICKS_CONTENT_TABLE`) — title-level metadata
- **External knowledge:** Wikipedia (already), IMDB / Gracenote (being evaluated — see 2026-05-07 notes)
- **Social signals:** Sprout Social (`SPROUT_SOCIAL_API_KEY`) — reaction/chatter graph per scene
- **Internal ground truth:** scripts, subtitles, editorial notes (where available)

## 3. Outputs

Per scene: a set of prompt objects (schema: `docs/schema/prompt-output.md`) with:
- `primitive` (trivia | scene_iq | poll | explainer | cast | send_to_phone | shoulder_content)
- `body` (text / multiple_choice options / poll options)
- `supporting_text` (drawer/side window detail)
- `source_citations[]`
- `quality_scores` (relevance, intrigue, safety, redundancy)
- `hitl_state` (pending | approved | rejected | edited)
- `monetization_eligible` (bool + advertiser categories)

## 4. Architecture sketch

```
Tubi Moments JSON  ──┐
Databricks metadata ─┤
Wiki / IMDB / GN  ───┼─▶  Feature extractor  ──▶  Use-case selector  ──▶  Prompt generator  ──▶  Ranker/safety  ──▶  HITL CMS  ──▶  Prompt store
Social signals    ───┘                                                      (LLM, per primitive)    (LLM + rules)           (approve/edit)
```

MVP = pre-generation + cache; no per-user inference at viewing time.

## 5. Approach to generation (from 2026-05-07 hackathon scoping)

Two strategies under evaluation:

| Strategy | Pros | Cons |
|---|---|---|
| **Find facts → match to scene** (current Tubi Moments approach; wiki-first) | Grounded, citable | Ceiling is wiki coverage; doesn't scale across catalog |
| **Take scenes → use model capabilities internally to generate** | Scales across catalog; richer prompts | Knowledge cutoff risk, lower reliability, higher HITL overhead |

**MVP decision (tentative):** hybrid — grounded lookups for facts that need citations (cast, historicity, music) + model generation for opinion/explainer/poll primitives. Validated via eval set.

## 6. MVP scope

From hackathon planning:
- Extract scene + moments data into JSON (done, per Tubi Moments pipeline).
- Generate per-scene prompts for a limited title set (5–10 hero titles).
- Target the **CTV pause surface** at launch; prompts serialized per the target schema so mobile/web/proactive consume the same store in P2.
- Primitives we want to prompt for in MVP (see `docs/use-cases/primitive-catalog.md`):
  - SceneIQ facts (grounded)
  - BTS / trivia (fact)
  - Trivia (MCQ)
  - Cast cards
  - Explainers (editorial-only at launch)
  - "How real is it?" (legal / medical / historical / book-accuracy)
  - Cameo alerts
- Human-in-the-loop review before any prompt reaches a client surface.
- **Out of MVP for the pipeline:** per-user dynamic ranking, live inference at view time, conversational follow-up state.

## 7. Evaluation

See `docs/research/eval-strategy.md`. Dimensions:
- Factual accuracy (grounded facts)
- Scene relevance
- Tone / brand fit
- Safety (no legal/competitive issues)
- Intrigue / "would a user tap this?" (HITL + A/B downstream)

## 8. Open questions

- Which external knowledge providers beyond wiki — Gracenote? IMDB scraping?
- Schema for "use-case potential signals" (see 2026-04-30 notes).
- Ownership of CMS / HITL tooling (reuse Adrise or build new?).
- Caching architecture for multi-language / regional variants.
- How do we handle title refresh / continuity seasons of a series?
