# 2026-05-07 — [Hold] Scoping Hackathon Project

**Attendees:** Aryan Gupta, Lia Yu, Evan Aubrey, Rahul Rao, Aidean Sharghi, Aidan Connerly

## Notes

### Scoping

- **Title list:**
  - Already ran: Gladiator
  - Good output: Legally Blonde, Devil's Advocate, Wonder Woman
- We could use IMDB / Gracenote.
- **Rahul Rao + Aidean Sharghi** — look into Databricks.

### Goal
- Use model capabilities internally vs matching data sources.
- Currently, pulling wiki data and matching to scenes.
- Can't scale if we only limit to wiki / IMDB.
- Generate & use eval / data sources to verify.

**Note:**
- Knowledge cutoff.
- Reliability is lower.
- Human overhead increases.
- Find facts → match to scene vs take scenes and find facts.

### MVP
- Extract scene + moments data into JSON.
- Generate trivia/BTS for those scenes.
- Human in the loop.

### What interactions/categories do we want to prompt for in MVP?
- Trivia / Polls
  - Fact trivia
  - Opinion
- How real is it
  - Legal
  - Medical
  - Historical
  - Accuracy to the book if fictional
- Facts — should be grounded.
- Moments data (scene — actor / music / etc.).

### Output — example
- **Lia Yu** will share example prompt / output.

## Action items
TBD.
