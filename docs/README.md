# docs/

Source of truth for the SceneSense / SceneIQ / TubiX spec work.

Start here, then dive into whichever subtree maps to the question you're
trying to answer.

## The demo (start here)

- [LB demo final spec](research/lb_demo_final.md) — 6-card Legally Blonde bundle,
  cue-point-verified, card-by-card content + follow-ups + "USE in demo" markers.
- [LB demo UX walkthrough](research/lb_demo_ux_walkthrough.md) — step-by-step
  viewer flow, exactly what renders on screen at each tap.

The canonical JSON sits at `src/scene_sense/demo/legally_blonde.demo.json` and
is regenerated into `data/outputs/` by `scene-sense demo`.

## Vision
- [TubiX executive summary](vision/tubix-exec-summary.md) — strategy narrative (passive → interactive, watch graph → intent graph)
- [Platform walkthroughs](vision/platform-walkthroughs.md) — Saving Private Ryan (TV), Minority Report (mobile), Legally Blonde (mobile)

## PRDs
- [SceneSense master PRD](prds/00-scenesense-master.md) — umbrella spec; links to the three sub-PRDs
- [Content Intelligence PRD](prds/01-content-intelligence.md) — pipeline that generates scene-level prompts
- [Client Experience PRD](prds/02-client-experience.md) — user-facing surfaces (pause, proactive prompts, mobile dual-screen)
- [Monetization PRD](prds/03-monetization.md) — how SceneSense surfaces become premium ad inventory
- [SceneIQ PRD](prds/04-sceneiq.md) — consolidated draft PRD for the scene-aware pause layer shipping on the Interactive Pause serving contract
- [Interactive Pause PRD (baseline)](prds/99-interactive-pause-baseline.md) — Yael's existing PRD that SceneIQ extends

## Architecture
- [Architecture overview (narrative)](use-cases/architecture-overview.md) — full 6-step pipeline
- Diagrams live in [`assets/`](assets/) — referenced from the top-level README.

## Schema
- [Tubi Moments schema](schema/tubi-moments.md) — derived from the current VLM output
- [Prompt output schema](schema/prompt-output.md) — internal record shape emitted by the pipelines
- `scene_sense.ui_schema.contract` — the **client-facing** card-type contract
  (pure Python; run `scene-sense validate` to check a bundle)

## Use cases
- [UX primitive catalog](use-cases/primitive-catalog.md) — trivia, polls, SceneIQ, cast, explainers, send-to-phone, shoulder content
- ["How Real Is It?" primitive spec](use-cases/how-real-is-it.md) — end-to-end grounded-expert pipeline (worked example on *Devil's Advocate*)
- [Generators runbook](use-cases/generators-runbook.md) — how to run realism + trivia pipelines on a title
- [Trivia architecture](use-cases/trivia-architecture.md) — 5-stage pipeline, tuning dials, error taxonomy

## Research (open threads)
- [Opportunity sizing](research/opportunity-sizing.md)
- [Legal considerations](research/legal-considerations.md)
- [Eval strategy](research/eval-strategy.md)
- [Competitive landscape](research/competitive-landscape.md)

## Meeting notes
- [2026-04-30 UX working session](meeting-notes/2026-04-30-ux-working-session.md)
- [2026-05-05 SceneSense planning](meeting-notes/2026-05-05-scenesense-planning.md)
- [2026-05-06 hackathon discussion](meeting-notes/2026-05-06-hackathon-discussion.md)
- [2026-05-07 hackathon scoping](meeting-notes/2026-05-07-hackathon-scoping.md)

## Archive

Superseded drafts (kept for historical reference, not maintained):
- [`archive/lb_sceneHRIT_v2.md`](archive/lb_sceneHRIT_v2.md) — pre-curation HRIT draft (replaced by `lb_demo_final.md`)
- [`archive/lb_realism_cards.md`](archive/lb_realism_cards.md) — v1 realism card dump
- [`archive/lb_viral_top25.md`](archive/lb_viral_top25.md) — exploratory viral-moments list
