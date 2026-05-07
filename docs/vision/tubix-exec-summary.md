# TubiX: The Next Evolution of Streaming

> CTV-first positioning. Dual-screen / mobile conversational / send-to-phone handoff are Phase 2+ and should not be led with. The raw planning-doc narrative is preserved at the bottom for reference.

## 1. Positioning

**TubiX is the next generation of interactive ad formats and in-player interactivity on CTV.** It extends the Interactive Pause inventory Tubi is already shipping with contextual, AI-driven formats — while simultaneously giving viewers genuine non-ad value at the pause screen (SceneIQ facts, trivia, cast, "explain this scene").

Two things happen on the same surface:

1. **For advertisers** — a new category of premium direct-sold inventory: sponsored SceneIQ cards, sponsored trivia, sponsored polls, "brought to you by…" title sponsorship. Extends Interactive Pause's $3.5M H2'26 opportunity into higher-CPM, scene-aware formats.
2. **For users** — the pause screen stops being an ad dead-end and becomes a moment of real utility: who's that actor, what just happened, what's the BTS story, what do other viewers think.

That dual value is the pitch. Mobile/web iteration and eventual dual-screen / conversational AI are follow-ons once CTV adoption and monetization are proven.

## 2. Why now

- Streaming UI has barely evolved in a decade. The grid + player hasn't changed. Users *already* second-screen during playback (Google, Reddit, IMDB) — but off platform, so Tubi captures none of the intent.
- Interactive Pause is already funded, scoped, and shipping on CTV WebOTT in H2'26. That's the surface to extend.
- Tubi is a FAST challenger — AVOD economics directly benefit from interactive depth (new inventory), whereas SVOD incumbents have weaker monetization incentives to invest here.
- Content differentiation is hard (non-exclusive libraries). UX differentiation is the lever Tubi has.

## 3. What TubiX delivers on CTV (MVP surface)

**Pause screen.** 5s post-pause, the user sees a SceneIQ card tied to the exact scene they paused on — plus remote-click-able follow-ups (trivia, cast, "explain this scene", polls). Dismisses on back or resume. Advertisers can sponsor the primitive ("Brought to you by…") or supply the creative (sponsored trivia, sponsored poll). All HITL-approved and scene-safety gated.

**Proactive prompts (Phase 1.5 / 2).** Opt-in button, like a closed-captions toggle. Same primitives, surfaced during playback for viewers who want more depth. Default off.

**Title sponsorship / takeover.** Fixed-fee sponsorship applied across all SceneSense prompts for a title, and/or a pre-roll bumper tying the sponsor to the scene-level experience.

## 4. What the platform adds beyond ads

- **SceneIQ facts** tied to the paused scene (grounded, cited, HITL-approved).
- **Cast / "Recognize her?"** with follow-up watchlist CTAs into Tubi catalog.
- **Trivia + Polls** (fact + opinion); polls surface aggregate reactions.
- **"How real is it?"** legal / medical / historical / book-accuracy explainers.
- **Explainers** for confusing moments.
- **Easter eggs / foreshadowing** for engaged viewers.
- **Character / relationship maps** on ensemble titles.

See `docs/use-cases/primitive-catalog.md` for the full catalog and MVP scope.

## 5. Data upside (strategic, not the pitch)

As a second-order effect, every prompt tap is a structured signal about what a viewer cares about in a scene. Over time this feeds an *intent graph* layered on the watch graph — smarter ranking, search, personalization. We don't lead with this because it's a long-term outcome, not an MVP deliverable, but it's why the investment compounds.

## 6. Phased rollout

| Phase | Focus | Timing (target) |
|---|---|---|
| **1 — CTV Pause MVP** | Passive pause-screen prompts + sponsored formats on major WebOTT platforms. Hero titles (5–10). | Aligned to Interactive Pause Go Live — **Sept 30, 2026** |
| **1.5 — Proactive opt-in on CTV** | "TubiX on" toggle surfaces prompts during playback. Same primitives. | Post-MVP stabilization |
| **2 — Mobile + web iteration** | Mirror CTV primitives; faster iteration loops; early programmatic explorations deferred. | Late 2026 / early 2027 |
| **2 — Dual-screen handoff** | "Continue on phone" as a convenience for deep rabbit-hole content. Send-to-phone for direct conversions (Fandango, storefronts, promo wallet). | Phase 2 |
| **3 — Scaled CTV + conversational AI** | Dynamic per-user prompt personalization, conversational follow-ups, shoulder-content integration (Project Encore). | Phase 3+ |

## 7. Cost mitigation

- MVP is **pre-generated + cached**, HITL-approved. No live per-user inference at launch.
- Title set starts narrow (5–10 titles) and expands as eval/HITL pipelines prove out.
- Grounded sources (wiki, IMDB, Gracenote) do the heavy lifting for factual primitives; LLM generation carries opinion/explainer/poll primitives where facts aren't needed.

## 8. First-mover vs. "me-too"

If the industry drifts toward in-player contextual intelligence (X-Ray is the baseline; peers will follow), Tubi pays the cost either way. Moving first preserves:
- A first-party data moat (intent graph).
- Differentiated positioning for sales in a non-exclusive content market.
- Partner/platform leverage (earned media, potential distribution benefits with non-competing partners).

The cost of waiting is giving SVOD/AVOD peers time to define the mental model for advertisers and viewers.

---

## Appendix — original planning-doc narrative

> Preserved verbatim below as source material for future edits. Not the current positioning.

### Executive Summary (original)

For over a decade, streaming has been defined by a static interface: scroll, select, watch, repeat. Across the industry, the grid hasn't meaningfully evolved. Content libraries have exploded, but the experience itself remains passive, and optimized for lean-back consumption in a world that has become fundamentally interactive. While watching TV, users look up actors, search for explanations, check Reddit reactions, and hunt for what to watch next — but they do it off platform.

TubiX is an LLM-powered engagement layer that will persist across the user journey on Tubi. By integrating conversational AI across the entire user lifecycle, from proactive discovery to real-time viewing, Tubi can capture the "dual-screen" habit, turning cobbled-together interactive experiences across various platforms — each lacking context from one another — into seamless interactive experiences within the Tubi app.

By providing this seamless experience to users, Tubi can convert fragmented second-screen curiosity into structured first-party intent data. While the short-term tradeoff will involve disruption to passive ad consumption and incremental AI cost, the long-term payoff is a robust and competitive data moat:

- **Explicit Intent Data** — guessing preferences from clicks → knowing intent from natural language → better recommendations, ad targeting, data flywheel.
- **Premium Ad Integration** — interactive AI moments (polls, trivia, shop the look) create new direct-sold inventory.
- **Differentiated sticky experience** in a non-exclusive content market → share shift.

This is a strategic shift from maximizing passive ad impressions per session to maximizing intelligence per session.

### The In-Player Experience (original)

TubiX makes streaming responsive without making it complicated. Subtle, well-timed prompts on pause screens surface SceneIQ facts, cast info, explainers, polls. Follow-ups feel almost psychic. No typing, no context switching, no explaining what scene you're on. On TV, interaction stays lightweight; on mobile, rabbit-hole conversation can unfold.

### The Data Shift (original)

Every prompt tap is a structured signal of deeper motivation — character psychology vs. plot mechanics, realism vs. conspiracy, controversy vs. lore. Over time, TubiX builds an intent graph layered on top of the watch graph.

### FAST vs SVOD (original)

In a non-exclusive content ecosystem, UX is the differentiator. AVOD benefits directly from interactive depth via new inventory; SVOD does not have the same monetization incentive. Tubi as a challenger brand has more UX flexibility.

### Shoulder Content (original)

TubiX extends into catalog depth — explainers, breakdowns, expert commentary. Project Encore brings creator shoulder content in-house, shares revenue, and compounds retention with in-view engagement.
