# Interactive Pause PRD (Baseline)

> **This is the existing PRD from Yael Lazarus — pasted verbatim so we have it locally as the foundation we extend. SceneSense's client/monetization PRDs build on top of this.**

**Team / Workstream:** <insert team name>
**Contributors:** Yael Lazarus, Radu Dutzan
**Status:** Draft
**Last Updated:** Apr 23, 2026

## 1. TL;DR & Discussion Topics

| # | Topic |
|---|---|
| 1 | **[FYI]** Interactive Pause Ads are prioritized as a H2 Ad Format release by sales and product leadership. This feature represents a $3.5M revenue opportunity over the course of the first 12 months. |
| 2 | **[FYI]** Interactive Pause Ads are ad formats initiated only when users pause content, offering a less intrusive way to surface advertising creative in-stream. They include remote-click interactivity, allowing users the opportunity to engage with the creative and potentially offer advertisers lower-funnel conversions. |
| 3 | **[Steer]** Interactive Pause Ad formats will be limited to direct-sold campaigns at launch to maintain complete control over creative execution. |
| 4 | **[Steer]** Interactive Pause Ad formats should run on all major WebOTT platforms, but will not be available on Roku at launch. Post-MVP: extend to mobile, customizing CTAs per platform. |
| 5 | **[Steer]** Interactive Pause Ad formats will follow current pause-ad serving logic — surface 5s after the user pauses, dismiss when user hits back or resumes playback. |
| 6 | **[Steer]** Impression pixels fire when the creative initially renders to track ad delivery. A subsequent engagement pixel fires on creatives where users surface another frame. Example: trivia — pixel 1 on question render, pixel 2 on answer render. |
| 7 | **[Steer]** Interactive elements: MVP = QR code, Trivia, Carousel. Phase 2 = Poll, Dynamic Countdown, Send-to-Phone. |
| 8 | **[Steer]** Interactive Pause Ad creative will leverage iFrames. |

## 2. Understand

### a. Problem / for whom
- Moving beyond awareness: engagement opportunities within ads allow us to provide performance metrics to advertisers.
- Conversions: give users the opportunity to engage with lower-funnel marketing opportunities.
- Less-intrusive ad experience: user-initiated format creates incremental inventory without increasing ad load.

### b. Why it's real
- Identified as H2 2026 sales priority.
- Interactive ad formats on Tubi today are limited to homegrid; this is the first in-stream interactive format.

### c. Goals

| # | Goal | Metric | Target |
|---|---|---|---|
| 1 | Create more ad formats that offer interactivity | Engagement rate | TBD |
| 2 | Create incremental ad opportunities without increasing ad load | Revenue, Ad Load | TBD |
| 3 | Provide advertisers with performance metrics | Engagement rates | TBD |

### d. Non-goals
| # | Non-goal | Why |
|---|---|---|
| 1 | Guaranteeing performance | Beta campaigns needed to establish benchmarks |
| 2 | Guaranteeing conversion | Same |
| 3 | Unlocking programmatic demand | Direct-sold only at launch for creative control |
| 4 | Adrise click tracking | Out of scope pending engagement data |
| 5 | Poll analytics within Adrise | Out of scope for MVP |
| 6 | Ad serving progressive screens | Out of scope |

### e. Product vision
- Tubi offers a suite of interactive opportunities within pause state.
- Tubi can match interactive opportunity to advertiser vertical and goal.
- UI is engaging and non-intrusive.
- Performance benchmarks meet or beat industry standard.

### f. Testing
Working hypothesis / experimentation plan TBD.

### g. Workback plan

| # | Target date | Milestone |
|---|---|---|
| 1 | Apr 30, 2026 | Draft Requirements |
| 2 | May 14, 2026 | Designs |
| 3 | Jun 19, 2026 | Align on technical approach |
| 7 | Jun 19, 2026 | Marketing materials |
| 4 | Jul 1, 2026 | Build |
| 5 | Aug 14, 2026 | QA |
| 6 | Aug 31, 2026 | Ship |
| 8 | Sep 11, 2026 | Campaign Ops |
| 9 | Sep 25, 2026 | Launch Readiness |
| 10 | Sep 30, 2026 | Go Live — first closed beta campaign |

### h. People

| # | Role | Who | R/S/I |
|---|---|---|---|
| 1 | PM | Yael Lazarus | Responsible |
| 2 | PM | — | Responsible |
| 3 | PD | Radu Dutzan | Responsible |
| 4 | OTT Eng | Arun Shankar | Support |
| 5 | OTT Eng | Marcelo Cabral | Support |
| 6 | QA | Arif Ahmed | Support |
| 7 | PM (PMM) | Rahul Kothari | Informed |
| 8 | UXR | Ibrahim Abbas | Informed |
| 9 | MS | Andrew Zoss, Caitlin Bell | Informed |
| 10 | AM | Carla Echevarria, Tyler Kahn | Informed |

### i. Alignment

| # | Approved | Reviewer | Notes |
|---|---|---|---|
| 1 | In-Review | marko.ma@fox.com | V1 PRD |

## 3. Solve — Key Features

### 1. QR Code inclusion in Interactive Pause creative (MVP)
As a PM, I want to append a custom QR code to pause ad creatives so users can extend interaction to a second screen via mobile. QR codes are created in-house with the Tubi QR code generating tool so I can determine the landing page, generate an image, and track reporting via the dashboard.

**User flow:** User presses pause → pause ad creative with QR code appears after 5s → user scans → user opens a specific landing page on mobile → scan tracked via QR code tracking page → user can dismiss pause ad at any time.

Size: S. Priority: — (see QR Code PRD).

### 2. Trivia (MVP)
As a PM, I want to present users with trivia questions and surface multiple-choice options to select answers from.

**User flow:** pause → creative appears after 5s → includes trivia question (e.g. "What was the name of Ross' pet monkey on *Friends*?") → multiple choice, scroll with remote → select → new creative renders with correct answer.

**Impression pixels:** server-side pixel on question render; client-side pixel on answer render.

Size: S. Priority: Must Have.

### 3. Carousel (MVP)
As a PM, I want to present multiple images within the pause ad creative that users can scroll through.

**User flow:** pause → pause ad creative with one larger central image + up to 5 smaller thumbnails below → tap thumbnail to promote to center. Design can be modified to include QR codes on the right for further second-screen engagement. Post-MVP: send-to-phone buttons instead of QR.

Size: S. Priority: Must Have.

### 4. Send-to-Phone
As a PM, I want a "send to phone" button on creatives trafficked to authenticated Tubi users with the app installed. Selecting triggers a push/inbox card with brand + tagline + tappable link.

Apps:
- Fandango (send showtimes)
- Amazon storefront (shop on Amazon)
- "Get it delivered" (doordash / instacart / gopuff / etc.)

URL landing pages:
- Make an Appointment → showroom locations near user
- Find a store → store locations near user

Unauthenticated fallback: QR code.

Size: S. Priority: Must Have (see Send to Device PRD).

### 5. Send-to-Phone (promo wallet)
Include a "send to phone" button on creatives trafficked to authenticated users with the Best Network pass in their mobile wallet, so they can redeem promotions attributable to ads on Tubi.

**Flow A (auth):** pause → creative with "redeem promo" → remote click → push/inbox card "Add to wallet" → tap to download.
**Flow B (unauth):** pause → QR code → scan → download pass to wallet.

### 6. Polls (Phase 2)
Present users with a prompt and multiple-choice options. Scroll with remote → select → new creative renders bar graph with aggregate results within xx time frame.

Impression pixels: pixel 1 on question render, pixel 2 on results render.

### 7. Countdown (Phase 2)
Present a countdown UI reflecting time remaining for a brand moment (release, launch). Dynamic Day/Hour/Min/Sec ticking while on screen.

## 3b. Key Flows
Designs: *Vibes* (placeholder — Figma link to be added).

## 3c. Communication
TBD (Slack channel, email, meeting invite).

## 3d. Launch Checklist

| # | Team | Consideration | Action owner |
|---|---|---|---|
| 1 | Analytics | Tracking needs | Gozde Cavdar |
| 2 | Content Acquisition | Curation impact | Lady Learned, Alexis Franklin |
| 3 | Content Operations | CMSUI changes | Arthur Kim, Davis Ancona, Yiming Chen |
| 4 | Customer Support | Support content / training | Bilan Jenkins |
| 5 | International | Multi-country launch | Christina Peyser |
| 6 | Legal | Legal ramifications | Nicole Lodge |
| 7 | Marketing | GTM plan (pricing, packaging) | Seth Shamban |
| 8 | Product Operations | Dogfooding / launch mgmt | James Jones, Jenny Ong |
| 9 | Sales | Sales enablement | TBD |
| 10 | Security | Risk vector | TBD |

## 3e. Key decisions / open issues / revisions
TBD.
