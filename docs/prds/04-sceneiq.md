# SceneIQ — Draft PRD (discussion)

**Status:** Early draft for discussion. Nothing here is scoped or committed — most of it is still open. Language is intentionally tentative.
**Owner:** Rahul Rao
**Partners:** Yael Lazarus (Ads PM), Rahul Kothari (PMM), Design, Sales, Legal, Analytics
**Last updated:** 2026-05-11

---

## 1. TL;DR

SceneIQ is a proposal for a **scene-aware layer on the Tubi pause screen** that would sit on the Interactive Pause surface and reuse its direct-sold ad stack. The idea is to make pause-state creative (and a set of editorial companion primitives) relevant to the specific scene the viewer just paused on, rather than generic.

Two value props on one surface:

- **For advertisers** — potentially a new category of premium direct-sold CTV inventory, where the creative ties to the moment rather than just the title.
- **For viewers** — real non-ad utility at pause (a scene fact, cast, a quick explainer, "how real is it?") so pause stops being dead air or a generic ad break.

The strategic question we're trying to answer this week is whether scene-awareness is a strong enough differentiator to justify a CPM premium over Interactive Pause, and what the right framing and packaging look like for a potential Sept 30, 2026 beta (shared Go Live with Interactive Pause).

We are explicitly *not* trying to decide mobile, dual-screen, send-to-phone, or conversational AI yet.

---

## 2. Problem we're trying to solve

**For advertisers.** Interactive Pause gives us remote-click CTV creatives (QR, trivia, carousel, and later polls, countdown, send-to-phone). These are a real step up from static pause ads, but the creative is still generic — it runs the same whether the viewer paused on a courtroom scene or a back-to-school scene. Any CPM premium story beyond the Interactive Pause baseline probably depends on scene relevance that Interactive Pause alone doesn't produce.

**For viewers.** Pause today is usually dead air or a surface for an irrelevant ad. We believe viewers already go off-platform during pause to satisfy scene-level curiosity (actors, realism, "is that real?", what's the song), but Tubi captures none of that intent or engagement.

**For Tubi.** The catalog is non-exclusive — UX is the lever we have to differentiate. Peers (X-Ray is baseline; SVOD discovery layers are moving; FAST peers will follow) will define the in-player interaction paradigm for advertisers and viewers if we wait.

We're not yet sure which of these three framings is the right one to lead with externally. That's part of the PMM conversation.

---

## 3. Why now

- Interactive Pause is already funded and shipping H2'26 on CTV WebOTT with a $3.5M / 12-month direct-sold opportunity. Anything we layer on inherits that surface and that launch.
- Walmart is a named content partner with content ready Nov 2026. Their stated asks (dynamic creative messaging tied to relevant scenes + frictionless conversion) map naturally to what a scene-aware layer would do.
- AVOD/FAST economics directly reward interactive depth via new direct-sold inventory. SVOD peers have weaker incentive to build this, which may give us a window.

---

## 4. What SceneIQ could look like

A scene-aware layer on top of the Interactive Pause surface. Same 5s-after-pause render, same iFrame delivery, same direct-sold constraints, same WebOTT-minus-Roku footprint. Scene-awareness would show up in two ways:

### 4a. Scene-aware versions of Interactive Pause formats

The existing Interactive Pause creatives (QR, trivia, carousel) rendered with scene-informed copy, product assortments, or MCQs. Example: a Walmart carousel on a back-to-school scene shows back-to-school assortment; the same carousel on a kitchen scene shows grocery. Same component family, scene-driven creative selection.

### 4b. Net-new editorial primitives

Things Interactive Pause doesn't cover, that give viewers real utility at pause even when the slot isn't sold. Working set we'd want to discuss:

- **SceneIQ card** — a concise grounded fact about what just happened.
- **Cast / "Recognize her?"** — who's on screen, one compelling fact, optional watchlist CTA.
- **"How real is it?"** — expert-framed realism explainer (legal / medical / historical / book-accuracy), with a persistent disclaimer.
- **Explainer** — plain-language breakdown of a confusing moment; editorial-only for legal reasons.
- **Cameo alerts, easter eggs, BTS facts** — mostly editorial at MVP.

Some of these could carry advertiser attribution (SceneIQ card, cast, "How real is it?"); others stay editorial-only at launch.

**Sponsorship wrappers** on top of either family:
- Title sponsorship — "Brought to you by…" chrome across all SceneIQ cards on a title.
- Title takeover — sponsorship + pre-roll bumper + advertiser-category lock for the title window.

### 4c. What it might look like on screen

Still a design question, but the working model is:

1. User pauses.
2. After 5s (matching Interactive Pause serving logic), a primary card renders.
3. The primary is a SceneIQ primitive (sponsored or editorial) when the scene is eligible; otherwise we fall back to a standard Interactive Pause creative.
4. A small number of follow-up chips (remote-click) let the viewer chain into a related primitive or drawer.
5. Dismiss on back or resume.
6. Account-level toggle, per-title toggle, and reduced-motion / accessibility settings.

Still open: whether primitives only surface on pause (passive, lower-risk) or can surface during playback (proactive, higher-intent but more intrusive). UXR to validate density and receptivity.

### 4d. What the back-end would need to produce

Pre-generated, HITL-approved, scene-level content per title — with source citations for anything monetizable — stored so the client can request the best-eligible prompt at pause. Guardrails we'd likely want to commit to early:

- **Pre-generated and cached.** No live per-user inference at view time — keeps cost and latency bounded.
- **Source-grounded + HITL-approved.** Nothing reaches a client unless a human has cleared it.
- **Auditable.** Per-prompt audit trail for legal + brand-safety review.

Exactly what that pipeline looks like is a separate conversation. We've prototyped pieces of it (Tubi Moments enrichment + grounded-fact generation) but the production-ready version is scope we'd need to commit to independently.

---

## 5. How this could be monetized

Three axes worth discussing. Every number below is a starting point for the sales conversation, not a commitment.

**Per-primitive CPM (Tier A).** Advertiser buys a scene-aware primitive type on a title at a CPM premium over the generic Interactive Pause floor (<10–12). Working hypothesis for the premium is around +30%, to validate.

**Title sponsorship (Tier B), flat fee.** "Brought to you by…" chrome across all SceneIQ cards on a title for the sponsorship window.

**Title takeover (Tier C), flat fee.** Tier B + pre-roll bumper + exclusive advertiser-category lock on the title for the window.

**SOV layered on any of the above:**
- **100% SOV** = title takeover.
- **Category-exclusive SOV** — advertiser is the only one in their category on a title; non-competing categories run alongside. Elegantly solves competitive-brand-adjacency.
- **Rotational SOV** — multiple advertisers share the title's SceneIQ inventory at defined percentages. Lower per-advertiser price, more addressable demand.

**Campaign extensions to think about:**
- *Dynamic creative messaging* (Walmart ask) — scene-tag-driven selection between advertiser-supplied creative variants.
- *Frictionless conversion* — QR in-creative to advertiser landing page (MVP-feasible); send-to-phone inherits Interactive Pause P2 timing.
- *Retargeting signal* — SceneIQ engagement events potentially feed on-Tubi retargeting or a 3P data partner (Sierra etc.) for social / open-web retargeting. Privacy + legal need to clear before we claim this.
- *Promo / coupon surfacing* — in-primitive promo with "redeem" CTA. Unclear if MVP or P1.5.

**Open questions on money:**

- Is SceneIQ sold alongside Interactive Pause at the premium, or as a separate SKU? (Shared simplifies the sales story; separate protects the premium.)
- Cannibalization — when a SceneIQ primitive replaces a generic IP creative in the slot, how much of that revenue is incremental vs. substitutional? Needs Analytics modeling.
- Is SceneIQ only a pause thing, or does it extend into mid-roll ad pods? Probably P1.5+ but worth not ruling out early.

---

## 6. Walmart as a worked example

Worth spending time on because (a) they're a named partner with a real deadline, (b) their asks already look like scene-aware inventory, (c) CPG/retail is the natural lighthouse vertical for other POCs.

**Their asks map directly to things we'd want to build:**

| Walmart ask | How SceneIQ would deliver |
|---|---|
| Dynamic creative messaging — customized Walmart spots + assortments after relevant scenes | Scene-aware carousel (Tier A sponsored) + title sponsorship chrome (Tier B). Scene tags drive assortment selection. |
| Frictionless conversion — QR / send-to-phone to complete purchase | QR at MVP; send-to-phone inherits Interactive Pause P2 timing. |

**What "excite & delight" means here.** A scene-aware back-to-school carousel framed as a helpful tip ("season's must-haves for this moment") probably outperforms a direct price ad. Scene-awareness only wins if it feels *useful at that moment*, not just *targeted*. UXR input matters a lot.

**Three outcome framings to orient around:**

- **Best case** — engagement on Walmart-sponsored primitives visibly beats a matched generic IP creative; QR conversion is meaningful; Walmart renews. We get a +30% CPM premium story with a lighthouse reference.
- **Middle case** — engagement modestly beats IP baseline; conversion is unclear; treated as experimental. The internal story holds, external pitch needs more data.
- **Worst case** — engagement is indistinguishable from IP baseline; gets written up as co-marketing. We'd need a second-vertical POC to defend the premium story.

**What we'd measure beyond CPM.** Engagement lift vs. matched IP baseline, QR scan + landing-page action, retargeting audience size (if retargeting clears privacy), brand-lift vs. control. Pick 2–3 for the external story; rest stay internal.

**Verticals to stress-test alongside Walmart (pick one):**
- Auto — "Recognize this car?" into dealer finder.
- Insurance — "How real is it?" sponsorship on courtroom / medical scenes. Unusual, potentially distinctive.
- Entertainment — theatrical release tied to genre-adjacent scene.
- QSR / delivery — natural send-to-phone partners, but P2, so less MVP-relevant.

---

## 7. What we're explicitly not doing (yet)

- Dual-screen / "continue on phone" handoff.
- Mobile + web surfaces.
- Send-to-phone ad formats (inherits IP P2 timeline).
- Conversational AI or chat UI.
- Live per-user LLM inference at view time.
- Per-user dynamic prompt personalization.
- Programmatic demand.
- Catalog-wide rollout (small hero-title slate at MVP).
- Roku.
- Performance / conversion guarantees in a beta.

Most of these are P1.5+ or P2+. We're not ruling anything out long-term; we're just not scoping it into the September beta conversation.

---

## 8. Open questions for this week

Grouped by the conversation they belong to, not by priority.

**Framing + naming (PMM).**
- Is "SceneIQ" the right name? Trademark / clearance?
- Lead with advertiser value, viewer value, or both — and does it depend on channel (sales vs. press vs. internal)?
- Competitive foil — beating X-Ray on monetization depth, or category-defining?
- How firmly do we suppress dual-screen / conversational in external comms?

**Packaging + pricing (Sales + Ads Product).**
- SKU structure — part of the Interactive Pause package, or a separate premium SKU?
- CPM premium numbers per primitive. Is +30% the right target?
- SOV tier pricing (100% / category-exclusive / rotational).
- A shared revenue calculator we can bring into sales conversations.
- Promo / coupon — MVP or P1.5?
- Retargeting signal — feasible, and what's the 3P partner + privacy story?

**Scope + proof points.**
- Hero-title slate (how many, which ones) and demo title for the sales deck.
- Headline primitives for the pitch — which 3–5 lead the advertiser story; which 1–2 lead the viewer story.
- Walmart as hero POC + one non-retail vertical to stress-test.
- Target advertiser list for POC outreach.
- Minimum beta size to defensibly claim engagement lift or CPM premium.

**Risk + guardrails.**
- Brand safety as a *product feature* in the sales pitch — framing HITL + source grounding + category checks as a sales asset.
- Source-citation standard in-UX.
- Competitive-brand adjacency — pipeline auto-check or ops-manual at launch?
- Crisis comms plan if an AI-generated prompt goes wrong externally.

---

## 9. Appendix — source material

- Interactive Pause baseline PRD: `docs/prds/99-interactive-pause-baseline.md` — the ad-serving spec SceneIQ would ship on.
- Master PRD (umbrella): `docs/prds/00-scenesense-master.md`
- Client Experience PRD: `docs/prds/02-client-experience.md`
- Monetization PRD: `docs/prds/03-monetization.md`
- Vision narrative: `docs/vision/tubix-exec-summary.md`
- Primitive catalog: `docs/use-cases/primitive-catalog.md`
- Research (open threads): `docs/research/opportunity-sizing.md`, `competitive-landscape.md`, `legal-considerations.md`
- Planning notes: `docs/meeting-notes/`
