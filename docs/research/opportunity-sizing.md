# Opportunity sizing — open research

**Owner:** Rahul Rao (with Yael Lazarus); inputs needed from Rahul Kothari, Caitlin Bell, Andrew Zoss.

> **Framing:** SceneSense monetization is a CTV-first extension of Interactive Pause. Opportunity sizing focuses on scene-aware premium direct-sold CPMs on CTV WebOTT and title-level sponsorships. Send-to-phone, mobile SceneSense, and dual-screen monetization are sized as P2 follow-ons.

## Baselines
- **Interactive Pause:** $3.5M over 12 months (direct-sold, CTV WebOTT).
- Current interactive ad formats are limited to homegrid.
- Baseline pause-ad floor CPM: <10–12 per 2026-05-05 notes.
- SceneSense target premium vs. baseline: **+30%** (draft, to validate with sales).

## Inputs we need
1. **Pause volume** per platform, per hero-title cohort (analytics — Gozde Cavdar).
2. **Scene-aware eligibility share** — what fraction of pauses land on a SceneSense-eligible scene (depends on title and primitive set).
3. **Engagement rate** for SceneSense primitives vs. Interactive Pause baseline (TBD from beta).
4. **CPM premium tiers** per primitive.
5. **Direct-sold fill rate** assumptions.
6. **Title sponsorship / takeover pricing** — fixed fee ranges per title tier (sales input).

## MVP (CTV) model skeleton

```
CTV MVP SceneSense revenue ≈
    Σ_primitives  ( pause_volume
                    × scenesense_eligible_share
                    × surface_share
                    × engagement_rate
                    × fill_rate
                    × CPM / 1000 )
  + Σ_titles     ( fixed_sponsorship_fee_per_title )
  + Σ_takeovers  ( takeover_fee_per_title )
```

## P2 follow-on sizing (not in MVP)

- Send-to-phone formats (Fandango, Amazon storefront, delivery, Best Network wallet) — CPA/CPC hybrid, attribution model TBD.
- Mobile SceneSense inventory — direct-sold first; programmatic demand evaluation pending sales.
- Dual-screen handoff conversion — size via push open rate × conversion rate × advertiser fee.

## Questions to resolve
- Is SceneSense sold **alongside** Interactive Pause (same package) or **as a separate SKU** with premium pricing?
- Cannibalization: if SceneSense replaces an Interactive Pause creative on high-engagement titles, what's the incremental vs. substitute revenue split?
- Walmart partnership (Nov 2026): guaranteed revenue or experiential-only commitment?
- Is there a data-package tier (anonymized poll aggregates / intent signals) that could add a late-stage revenue line?
