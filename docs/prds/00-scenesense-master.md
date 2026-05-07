# SceneSense / TubiX — Master PRD

**Status:** Draft (scaffold)
**Owner:** Rahul Rao
**Last updated:** 2026-05-07

> Umbrella PRD. Framing: **CTV-first interactive ad formats + in-player interaction value**. Mobile, dual-screen, and conversational are explicitly P2+. See `docs/vision/tubix-exec-summary.md` for the positioning narrative.

## 1. TL;DR

SceneSense is the content-intelligence layer behind **TubiX** — a CTV-first extension of Tubi's Interactive Pause inventory. It turns the pause screen into (a) a new category of premium direct-sold ad formats — sponsored SceneIQ cards, sponsored trivia, sponsored polls, title sponsorships — and (b) a genuinely useful in-player interaction surface for the viewer (facts, cast, explainers, polls). MVP is pre-generated + HITL-approved content on a narrow hero-title slate; scale and personalization come after.

## 2. Problem

- **For advertisers.** Interactive Pause unlocks CTV interactive formats (QR, trivia, carousel, countdown, send-to-phone). They're a big step up from static pause ads, but they're still generic — not tied to the scene the viewer just paused on. Advertiser differentiation / CPM premium depends on relevance.
- **For viewers.** Pause is a dead zone or — worse — a surface for irrelevant ads. Viewers already go off-platform (Google, Reddit, IMDB) to answer the curiosity the scene just raised. Tubi captures none of that intent.
- **For Tubi.** Non-exclusive content libraries mean the grid alone can't be our differentiator. UX flexibility is the lever. Every month we wait, peers (X-Ray, Netflix's AI search, FAST peers) define the paradigm.

## 3. Goals / Non-Goals

### Goals (MVP)
1. Ship a **scene-aware pause experience on CTV** (WebOTT first) on a hero-title slate, with SceneIQ facts, trivia, cast, polls, "how real is it?", and explainers.
2. Enable **sponsored SceneSense formats** as premium direct-sold inventory extending Interactive Pause.
3. Stand up the **Content Intelligence pipeline** (moments → prompts → HITL → prompt store) so scale follows, not retrofits.
4. Instrument engagement rigorously so sponsorship CPM premiums can be defended with data.

### Non-Goals (MVP)
1. **Dual-screen / send-to-phone / "continue on phone" flows.** Phase 2.
2. **Mobile and web** — fast-follow for iteration, but CTV ships first.
3. **Conversational AI** on any surface. Phase 2+.
4. **Live per-user LLM inference at view time.** Pre-gen + cache only at MVP.
5. **Programmatic demand for SceneSense-sponsored formats.** Direct-sold only at launch (mirrors Interactive Pause stance).
6. **Catalog-wide rollout.** 5–10 hero titles at MVP.
7. **Roku at launch** (mirrors Interactive Pause).

## 4. Sub-PRDs

| Area | Doc | What it covers |
|---|---|---|
| Content Intelligence | [`01-content-intelligence.md`](01-content-intelligence.md) | Pipeline: title → scenes → prompts (grounded + LLM + HITL) |
| Client Experience | [`02-client-experience.md`](02-client-experience.md) | CTV pause UX (MVP), proactive opt-in (P1.5), mobile/web (P2), dual-screen (P2) |
| Monetization | [`03-monetization.md`](03-monetization.md) | Ad formats, sponsorship tiers, opportunity sizing, CPM model |

The existing Interactive Pause PRD (Yael Lazarus) lives at [`99-interactive-pause-baseline.md`](99-interactive-pause-baseline.md) as the foundation this extends.

## 5. How this relates to Interactive Pause

SceneSense is **additive** to Interactive Pause:

| Interactive Pause (baseline) | SceneSense adds |
|---|---|
| Generic QR, trivia, carousel, countdown creatives | Scene-aware SceneIQ, trivia, polls, explainers tied to what the user just paused on |
| Direct-sold, iFrame-based creative | Same delivery model; SceneSense primitives generated + HITL-approved server-side |
| Engagement pixels (render + interaction) | Same instrumentation + SceneSense-specific engagement fields |
| Sept 30, 2026 Go Live on WebOTT | SceneSense MVP targets the same window; can share the first closed-beta campaign slot |

The monetization PRD covers whether SceneSense ships as part of the Interactive Pause package or as a separate SKU (open question).

## 6. Success metrics (draft — needs analytics alignment w/ Gozde Cavdar)

| Category | Metric | Target (MVP) |
|---|---|---|
| Engagement | % of eligible pauses with a SceneSense prompt tap | ≥ 15% |
| Engagement | Avg prompts tapped per engaged pause | ≥ 2 |
| Monetization | Sponsored SceneSense CPM vs. Interactive Pause baseline | +30% |
| Retention | 7-day return rate on titles with SceneSense enabled | +X pp |
| Cost | Pre-gen content cost per enabled title | < $Y |
| Quality | HITL approval rate of generated prompts | ≥ 90% |

## 7. Phased scope

| Phase | Scope | Targets |
|---|---|---|
| **MVP — CTV pause** | Major WebOTT (Roku excluded at launch). Hero title slate. Passive pause-screen prompts + sponsored formats. | Sept 30, 2026 |
| **P1.5 — Proactive opt-in on CTV** | "TubiX on" toggle; same primitives, during playback. | Post-MVP |
| **P2 — Mobile + web** | Mirror CTV primitives; first programmatic explorations. | Late 2026 |
| **P2 — Dual-screen / send-to-phone** | "Continue on phone" handoff; send-to-phone ad formats. | P2 |
| **P3 — Conversational + personalization** | Stateful conversational AI; dynamic per-user prompt ranking; shoulder content loop. | P3+ |

## 8. Open questions (tracked in `docs/research/`)

- CPM premium tiers per primitive (sales).
- Legal approval per use case (Nicole Lodge).
- Eval framework and HITL tooling ownership.
- Hero title selection criteria — which 5–10 titles.
- SceneSense shared surface with Interactive Pause creative: share the slot or separate slots?
