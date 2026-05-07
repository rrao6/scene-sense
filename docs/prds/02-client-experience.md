# Client Experience PRD

**Status:** Draft (scaffold)
**Owner:** Rahul Rao (PM); Radu Dutzan, Lia Yu, Evan Aubrey (design)
**Last updated:** 2026-05-07

> User-facing surfaces for TubiX. **CTV pause is the MVP surface.** Proactive prompts on CTV are Phase 1.5. Mobile, web, dual-screen handoff, and conversational AI are Phase 2+. Framing throughout is (a) interactive ad formats and (b) real playback interaction value — not dual-screen.

## 1. Platforms and surfaces

| Surface | Platform | Phase | Posture |
|---|---|---|---|
| **Pause screen** | CTV (major WebOTT; Roku excluded at launch) | **MVP** | Passive, remote-click only, scene-aware |
| Proactive prompt toggle | CTV | P1.5 | Opt-in via button (CC-style toggle); prompts surface during playback |
| Pause screen | Mobile, web | P2 | Mirror CTV primitives; iterate UX faster |
| Proactive on mobile | Mobile, web | P2 | Default off; opt-in via button |
| Dual-screen handoff | CTV → Mobile | P2 | "Continue on phone" for deep rabbit-hole content; send-to-phone ad formats |
| Conversational follow-ups | All | P3 | Stateful, post-session; feeds intent graph |

MVP rationale: CTV is where Interactive Pause inventory is already shipping, where the monetization story is strongest, and where Tubi has the most viewing volume. Mobile/web come along for iteration once CTV formats and eval/HITL are working.

## 2. MVP UX — CTV pause

### 2.1 Interaction flow

1. User hits pause.
2. After 5s (matching Interactive Pause serving logic), one **primary card** renders on the pause screen.
3. Depending on title/scene eligibility, the primary card is either:
   - A **SceneSense primitive** (SceneIQ fact, cast card, trivia, poll, explainer) — sometimes sponsored, sometimes purely editorial.
   - A **standard Interactive Pause creative** (QR, carousel, trivia per Yael's PRD) when SceneSense is not eligible or the ad-side targeting takes priority.
4. **Follow-up prompts** appear as remote-navigable chips alongside the primary card. Tapping chains into the next card / drawer.
5. A **"See More" drawer** can expand for long-form content (BTS deep-dives, "How real is it?" extended explainers).
6. Dismiss on back button or playback resume.

### 2.2 Density / budget

- Max 1 primary card on pause entry.
- Max 3 follow-up chips visible at once.
- Drawer open replaces the chip row but preserves dismiss.
- UXR (Ibrahim Abbas) to validate prompt density in concept testing.

### 2.3 Primitives shown on CTV MVP

Pulled from `docs/use-cases/primitive-catalog.md`. All HITL-approved and scene-safety gated:

- SceneIQ card (grounded fact)
- BTS / trivia (fact)
- Trivia (MCQ with reveal)
- Cast / "Recognize her?" → optional watchlist CTA into Tubi catalog
- Explainer ("Explain this scene")
- "How real is it?" (legal / medical / historical / book-accuracy)
- Cameo alert (where grounded + safe)
- Poll (opinion) — **behind HITL gate and legal review**; may slip to P1.5

### 2.4 Ad-aware behavior

- When a SceneSense primitive is **sponsored**, the creative is clearly attributed ("Brought to you by…" or advertiser branding per direct-sold spec).
- When SceneSense is **editorial-only**, no sponsorship chrome.
- When an **Interactive Pause creative** wins the slot (normal ad-serving logic), SceneSense follow-up chips may still surface *after* the ad's 5s render — depending on advertiser rules. Open question in `docs/research/eval-strategy.md` / monetization PRD.

### 2.5 Accessibility / settings

- Global "TubiX on/off" in account settings; per-title toggle available.
- Contrast / size parity with existing player UI.
- TTS compatibility where platform allows.
- Animation reduced-motion support.

## 3. Phase 1.5 — Proactive on CTV

- Opt-in via a dedicated toggle in the player HUD (analog: CC button).
- When on, subtle prompts surface during playback at eligible scene boundaries — never covering critical dialogue or action, respecting moderation tags.
- Same primitive set as MVP pause.
- Tap still pauses playback and expands into the pause-screen experience.

## 4. Phase 2 — Mobile + web

- Mirror the CTV primitives, adapted for touch + portrait.
- Drawer becomes full-screen portrait sheet; landscape keeps video visible.
- First programmatic demand explorations (if sales approves) for mobile-only inventory.

## 5. Phase 2 — Dual-screen handoff

Explicitly **P2, not the pitch.** When shipped:

- Authenticated users with the Tubi app on phone: "Continue on phone" push/inbox card.
- Unauthenticated: QR fallback.
- Used for deep rabbit-hole content (extended explainers, send-to-phone ad formats like Fandango showtimes, Amazon storefront, Best Network wallet promos).

## 6. Analytics (draft — w/ Gozde Cavdar)

Tracked events:

- `scenesense.prompt_impression` — primary card rendered
- `scenesense.prompt_tap` — user tapped primary card
- `scenesense.chip_tap` — follow-up chip tapped
- `scenesense.drawer_expand` — See More opened
- `scenesense.drawer_dismiss` — drawer closed
- `scenesense.session_end` — session rollup: prompts served, taps, dwell, categories

Sponsored variants carry an `advertiser_id` and mirror Interactive Pause's impression + engagement pixels.

## 7. Grouping / personalization (MVP is static; P2+ is dynamic)

- MVP: fixed rank per scene from the prompt store. No per-user personalization.
- P1.5: simple archetype-based reordering (e.g., the viewer taps lots of cast prompts → cast primitives surface first on the next title).
- P2+: full intent-graph-driven ranking.

## 8. Open questions

- Does SceneSense share the pause slot with Interactive Pause ads, or does it get its own slot? (Monetization + eng decision.)
- Prompt-density budget per pause — needs UXR validation.
- Can we surface a prompt before the 5s Interactive Pause render, or must we wait? (Ad-serving rules.)
- Localization plan for MVP hero titles — English-only at launch?
- Reduced-motion / TV-safe-zone design patterns for long drawer content.
