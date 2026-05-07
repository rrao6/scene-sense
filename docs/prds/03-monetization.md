# Monetization PRD

**Status:** Draft (scaffold)
**Owner:** Rahul Rao (PM); Yael Lazarus (PM, ads); Caitlin Bell, Andrew Zoss (sales)
**Last updated:** 2026-05-07

> CTV-first. SceneSense creates a new category of **scene-aware premium direct-sold inventory** extending the Interactive Pause surface. Send-to-phone and dual-screen ad formats are P2.

## 1. Thesis

Interactive Pause ($3.5M H2'26 opportunity) proves Tubi can ship interactive CTV formats. SceneSense makes those formats **scene-aware** — sponsorship ties to what the viewer just paused on, not a generic creative. That context is the CPM premium.

Net-new categories SceneSense unlocks on CTV:

1. **Sponsored SceneIQ card** — scene-aware fact card, advertiser-attributed ("Brought to you by…").
2. **Sponsored trivia** — advertiser-supplied or advertiser-adjacent MCQ with reveal.
3. **Sponsored poll** (P1.5+ subject to legal) — opinion prompt with aggregate reveal.
4. **Title-level sponsorship** — "Brought to you by…" applied across all SceneSense prompts for a given title.
5. **Pre-roll buyout / title takeover** — bumper at the start of content that includes SceneSense branding for the entire viewing.

Plus retained / extended Interactive Pause formats: QR, carousel, countdown, trivia baseline.

**P2 categories (not the launch pitch):**
- Send-to-phone direct-response formats (Fandango showtimes, Amazon storefront, delivery, Best Network wallet promos).
- Mobile SceneSense inventory (direct-sold first; programmatic exploration post-adoption).

## 2. Opportunity sizing (open — working with Rahul Kothari, Caitlin Bell, Andrew Zoss)

Inputs needed:

- Pause volume baseline on CTV WebOTT (already measured for Interactive Pause).
- Engagement lift from SceneSense scene-aware primitives vs. generic Interactive Pause creative (TBD from UXR + beta).
- Premium CPM tiers per primitive (sponsored SceneIQ vs trivia vs poll vs title takeover).
- Direct-sold fill rate assumptions.

Baseline references:
- Interactive Pause GTM floor: <10–12 CPM.
- SceneSense CPM premium target: **+30% over Interactive Pause baseline** (draft — see master PRD §6).

Model skeleton:

```
SceneSense annual revenue ≈
  Σ_primitives ( pause_volume × scenesense_eligible_share × surface_share × engagement_rate × fill_rate × CPM / 1000 )
+ Σ_titles   ( fixed_sponsorship_fee_per_title )
+ Σ_titles   ( takeover_fee_per_title )
```

Detail in `docs/research/opportunity-sizing.md`.

## 3. Ad format matrix (MVP = CTV)

| Format | Phase | Pricing model | Legal review |
|---|---|---|---|
| Sponsored SceneIQ card (CTV) | **MVP** | CPM + creative premium | Per use-case (Nicole Lodge) |
| Sponsored trivia (CTV) | **MVP** | CPM + engagement premium | Per use-case |
| Title sponsorship "Brought to you by…" (CTV) | **MVP** | Flat fixed fee per title | Per title |
| Pre-roll buyout / title takeover (CTV) | **MVP** | Flat fixed fee per title | Per title |
| Sponsored poll (CTV) | P1.5 | CPM + data-share premium | Per use-case |
| Mobile SceneSense sponsored formats | P2 | Direct-sold first; programmatic later | Per use-case |
| Send-to-phone (authenticated) | P2 | CPA / CPC hybrid | Per advertiser |
| Send-to-phone (QR fallback) | P2 | CPA / CPC hybrid | Per advertiser |
| Send-to-phone (promo wallet — Best Network) | P2 | CPA / flat | Per advertiser |

## 4. Pricing / packaging hypotheses (to validate with sales)

- **Tier A — Sponsored primitive (CPM + premium):** advertiser buys a scene-aware primitive at a CPM premium above Interactive Pause baseline. Delivery is programmatic within Tubi's direct-sold stack; creative execution is controlled.
- **Tier B — Title sponsorship (fixed fee):** advertiser pays a flat fee per title. SceneSense primitives on that title carry "Brought to you by…" chrome for the life of the sponsorship window.
- **Tier C — Title takeover (fixed fee):** Tier B + pre-roll bumper + exclusive advertiser category lock for the title.
- **Tier D — Data package (later):** anonymized intent signals (poll aggregates, category taps) sold back to advertisers / research.

## 5. Non-goals

- **No programmatic demand at launch** (direct-sold only; mirrors Interactive Pause).
- **No performance guarantees** during beta.
- **No Adrise click tracking / poll analytics in Adrise** at launch — out of scope pending engagement data.
- **No dual-screen / send-to-phone ad formats** in MVP — P2.

## 6. Legal guardrails (from 2026-05-05)

- Legal approves **each use case individually** before monetization. This applies to each SceneSense primitive.
- **Competitive-brand adjacency is blocked** (e.g., Coca-Cola ad during a Pepsi scene). Pipeline must check scene tags + brand mentions against advertiser category.
- Moderation-flagged scenes restrict advertiser pool.
- Right-of-publicity constraints on cast / "where are they now?" content.

Detail in `docs/research/legal-considerations.md`.

## 7. Content / partnership commitments

- **Walmart partnership:** content ready Nov 2026; experience commitment TBD.
- **NewFronts-adjacent beta:** first closed-beta campaign targeting **Sept 30, 2026** (aligns with Interactive Pause Go Live).

## 8. Relationship to Interactive Pause

Open question: is SceneSense sold **as part of** the Interactive Pause package, or as a **separate SKU**?

Arguments for shared:
- Same surface (pause), same ad-serving logic, same direct-sold ops.
- Simpler sales story at launch.

Arguments for separate:
- SceneSense carries a premium CPM (+30% draft target); conflating dilutes.
- Different creative approval path (HITL + legal per primitive).

Resolution needed with Caitlin Bell + Andrew Zoss + Yael Lazarus before sales enablement materials.

## 9. Open questions

- CPM premium tiering per primitive — exact numbers.
- Attribution model when SceneSense shares a surface with Interactive Pause ads.
- Reporting: Adrise dashboard vs. SceneSense-specific dashboard.
- Fill-rate assumptions for direct-sold-only MVP.
- Is "sponsored editorial" (advertiser name only, no creative) ok with legal and brand?
