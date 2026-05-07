# 2026-04-30 — TubiX UX Working Session

**Attendees:** Lia Yu, Evan Aubrey, Rahul Rao

## Notes

- Start with **TV** — monetizable. Web is secondary.
- UXR — validate via concept testing.
  - Use-case validation: types of content that resonate; where TubiX fits.
  - Survey testing.
  - Data gathering.
- Mobile is harder.
- Can AI start to generate these topics for us?
  - "What is most interesting for this title?"
  - North Star: conversational AI (later on).
  - Current: populate initial set of data using GenAI to scale.
  - Keep costs low, no live inference.
- **Aryan Gupta, Rahul Rao — Hackathon**
  - Tubi Moments Data (every title in catalog + cue_points).
  - Prompt engineering, platformize / automate / eval / human in loop.
  - This is our **Content Intelligence platform**.
  - It will likely consist of several small models behind 1 orchestration layer.

### Main jobs to be done
1. **Title and scene profiling:** understand content and generate structured attributes.
   - Requires a feature schema for titles aggregating:
     - Core title metadata
     - Structured content signals (synopsis, scripts, subtitles, chaptering)
     - Use-case "potential" signals (hardest to define — e.g., signals for a title with heavy lore or character mapping)
     - Public / social-media knowledge
2. **Use-case selection:** decide which engagement opportunities apply.
3. **Primitive mapping:** map each use case to the right UI primitive/format.
4. **Content generation:** generate prompts, polls, facts, quizzes.
5. **Ranking and filtering:** score for relevance, intrigue, tone match, safety, redundancy.
   - HITL evals → live in-prod data collection → eventually ML-automated ranking/evals.

### CMS layer
- May want manual/promotion additions.
- Need a human editing/feedback layer.
- Approve/deny for content-ops.

### MVP — UI Layer
- **BTS / Trivia**
  - How did they make this scene / extras
  - In-scene facts
- **Cast / Music / Location**
  - Cast: where are they now? Was this their big breakout role?
  - Cast: are there little-known actors at the time who are now huge and cameo here?
- **Explainers** — "help me understand what happened"
- **Character mapping / relationships**
- **Reactions** — "expert reactions" on mobile dual screen
  - Medical / Legal / Historical / Physical accuracy
  - How close is it to the book vs. real story?
  - How much did it cost? How much does it cost now?
- **Quizzes / Polls** — opinion vs. fact, character, controversial
- **Passive vs Interactive** (send to mobile / polls)
- **Proactive vs Passive**
  - Web/mobile more proactive
  - TV start with passive
- Should allow enable/disable.
- Group by series and movies.
- Which genres to pick? Which themes of UX?
  - Franchise
  - Nostalgia series

### Entry-points
- Pause
- Button (enable) — then can be proactive
- Future: proactive prompting during playback

### UX workflows
- TV
- Dual screen
- Mobile-only experience

### Concrete example
- Monetization examples (TBD)
