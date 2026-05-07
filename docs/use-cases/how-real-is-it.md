# "How Real Is It?" — Primitive Spec

**Status:** Draft v0.1
**Owner:** Rahul Rao (PM); eng support from hackathon team
**Last updated:** 2026-05-07
**Scope:** End-to-end pipeline that emits verifiable, expert-grounded realism prompts from Tubi Moments VLM output. Domain-parameterized (legal / medical / historical / military / science / book-accuracy / physical-stunt). Worked example: *The Devil's Advocate* (1997) at `data/samples/The_Devils_Advocate.json`.

## 1. Why this primitive gets its own spec

"How real is it?" is the single most legally exposed SceneSense primitive (medium-high per `primitive-catalog.md`). Defamation, right-of-publicity, and unsupported-expert-attribution risk are all concentrated here. Every realism prompt makes claims *about the world* (not about the fictional scene), so the grounding bar is higher than trivia / cast / SceneIQ — and the validator has to be stricter than an LLM-judge rubric alone.

It is also the highest-value primitive for certain verticals:
- **Legal titles** (*Devil's Advocate*, *A Few Good Men*, *My Cousin Vinny*, *Legally Blonde*) — sponsor fit: insurance, legal DTC (LegalZoom), law schools.
- **Medical procedurals** (*ER*, *House*, medical dramas) — sponsor fit: telehealth (Hims/Ro), pharma (OTC + DTC-health only; branded Rx is a bad interactive fit per legal).
- **Historical / war films** (*Saving Private Ryan*, *Oppenheimer*) — sponsor fit: History Channel, streaming competitors, museum partnerships.
- **Hacking / heist** (*Mr. Robot*, *Ocean's Eleven*) — sponsor fit: cybersecurity, fintech.

## 2. Inputs and outputs

### 2.1 Inputs
- **Tubi Moments JSON** per title (see `schema/tubi-moments.md`). Consumed fields per scene:
  - `scene_index`, `start_time`, `end_time`, `summary`
  - `content_desc.structured_data.themes_and_concepts`
  - `content_desc.structured_data.key_actions`
  - `content_desc.structured_data.dialogue_highlights`
  - `characters`, `detected_cast`
  - `content_tags`, `moderation_tags`
- **Title-level metadata** from `DATABRICKS_CONTENT_TABLE` (genre, release year, runtime).
- **External source bank** collected at title level (see §4.1): YouTube reactions, podcasts, legal-journal articles, academic papers, professional-media criticism.

### 2.2 Outputs
- N realism prompts per title, each tied to a specific `scene_index`, conforming to the extended prompt-output schema (see `schema/prompt-output.md` — realism extension). Each prompt carries HITL state, expert attribution with verbatim quotes, direct URLs with timestamps, and a grounding_type label.

## 3. Hard constraints (derived from the Devil's Advocate example)

These are validator-enforced, not prompt suggestions:

| Constraint | Enforcement |
|---|---|
| No fabricated expert names | Name must match a cross-referenced source (see §5.3). |
| No fabricated URLs | URL must resolve (HTTP 200) and the page body must contain the claimed quote. |
| No "unspecified expert" attribution | If the source can't name the expert, grounding_type demotes from `named_expert` → `generalized_source_supported`. |
| No generalized analysis sold as expert quote | Validator rejects prompts that lack a verbatim quote when `grounding_type = named_expert`. |
| No uncited claims about real-world accuracy | Every prompt requires ≥1 citable source — either direct expert or generalized domain source (e.g., ABA Model Rule text). |
| Competitive-brand exclusion applies | Pipeline runs the standard competitive-brand check on scene + advertiser (see `03-monetization.md`). |

## 4. Pipeline (title-level + scene-level)

```
┌─────────────────── TITLE-LEVEL (runs once per title) ──────────────────┐
│  1. Eligibility gate                                                    │
│  2. Domain classifier                                                   │
│  3. Source collection (grounding layer)                                 │
│  4. Source bank validation (URL resolve + quote match)                  │
└─────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────── SCENE-LEVEL (runs per eligible scene) ──────────────┐
│  5. Scene-claim extraction (from VLM output)                            │
│  6. Claim ↔ source binding (retrieval + LLM judge)                      │
│  7. Analysis & structuring (prompt generation)                          │
│  8. Anti-hallucination validator                                        │
│  9. HITL review                                                         │
│ 10. Emit prompt-output JSON                                             │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.1 Stage 1 — Eligibility gate

A title qualifies for `how_real_is_it` if any of:
- `content_tags` or title-level genre includes one of the target domains (legal-drama, medical-drama, war-film, historical-drama, hacking, heist).
- ≥5 scenes have `themes_and_concepts` containing a domain keyword (see `config/realism_domain_keywords.json`, not yet written).
- Manual allow-list override by content ops.

For titles that fail the gate, no realism prompts are generated.

### 4.2 Stage 2 — Domain classifier

Input: title metadata + the aggregated scene-level themes/key_actions.
Output: an ordered list of primary domains for the title (e.g., `["legal", "religious"]` for *Devil's Advocate*).

Cheap LLM call over a compressed title summary. Caches at title level.

### 4.3 Stage 3 — Source collection (grounding layer)

Goal: build a **Title Source Bank** of real, verifiable expert content. This is the stage the user's Step 1 prompt describes.

Per title + domain, collect candidate sources in tiered priority:

| Tier | Source type | Example |
|---|---|---|
| T1 | YouTube "lawyer/doctor/historian reacts" videos with named professionals | *2 Attorneys React* — Kaufman & Lynd |
| T1 | Podcasts featuring practicing professionals | *Westendorf & Khalaf PLLC* on *Devil's Advocate* |
| T2 | Academic / law-review / peer-reviewed | *Law & Literature Journal*, *Journal of the Legal Profession* |
| T2 | Journalist / critic writing with domain expertise | Vulture, Ars Technica, FiveThirtyEight, *The Atlantic* |
| T3 | Primary statutory / regulatory text (used for generalized-source-supported items) | ABA Model Rules, FDA guidance, IRS code |

**Retrieval:**
- Issue domain-tuned search queries (e.g., `"The Devil's Advocate" lawyer reacts scene`, `"Devil's Advocate" voir dire realism`, `"Devil's Advocate" professional responsibility`).
- Parse top ~50 results per query. For YouTube, fetch transcripts + timestamps. For articles, fetch body text + anchor headings.
- Tag each candidate: `title`, `url`, `publisher`, `author`, `author_class`, `retrieval_query`.

**Emit per candidate:** direct quotes (verbatim, 2–3 sentences) + timestamps or paragraph anchors + any cited statute / rule / primary source.

**Do NOT at this stage:** interpret, assess, or map to scenes. Stage 3 is ground-truth only.

### 4.4 Stage 4 — Source-bank validation

Reject any candidate that fails *any* of:
- URL does not resolve (HTTP non-200 or paywall without cached body).
- Claimed quote not found in fetched body (fuzzy match ≥0.92 against retrieved text).
- Author name not resolvable against LinkedIn / bar directory / PubMed / university faculty page (for named-expert tier only — generalized sources skip this check).
- Source is another AI-generated summary (reject AI-generated blog aggregators; allow academic papers about AI).

Validated sources land in the Title Source Bank with a `validation_hash` so downstream stages can prove non-fabrication.

### 4.5 Stage 5 — Scene-claim extraction

Per eligible scene, the generator reads the VLM output and extracts candidate **testable claims** — claims about the real world that the scene asserts or depicts. Not every scene qualifies; discard scenes where dialogue/action is not domain-specific.

For each extracted claim, emit:
- `claim_id`
- `claim_text` (the claim the scene makes about the real world, e.g., "Attorneys can cross-examine minors aggressively without judicial intervention")
- `scene_evidence` (verbatim from VLM: dialogue_highlights / key_actions that support the claim)
- `candidate_domain` (from stage 2)

Example (DA scene 4):
- `scene_evidence`: `key_actions = ["Cross-examining a witness", "Presenting a handwritten note", "Crying on the stand"]`; `dialogue = "A man's career... his reputation... his life is on the line!"`
- `claim_text`: "A defense attorney may conduct hostile cross-examination of a minor witness without judicial intervention."

### 4.6 Stage 6 — Claim ↔ source binding

For each `(claim, source)` pair:
- Embedding-based retrieval: cosine similarity between claim_text and source quote-chunks.
- LLM judge: "Does this source quote specifically address the claim? Yes / partial / no." Prompt must pass through the source's verbatim quote — no paraphrase.
- Retain bindings scored ≥0.8 and judged `yes` or `partial`.

Output per claim: ordered list of bound sources with relevance scores and the exact matched quote spans.

### 4.7 Stage 7 — Analysis & structuring

For each claim with ≥1 validated binding, generate the user-facing prompt. This is the user's Step 2 prompt, with stricter constraints:

**Prompt template (abbreviated):**

> You are generating a SceneSense realism prompt for the scene at `{start_time}`–`{end_time}` of `{title}`.
>
> You may ONLY use the attached bound sources — do not introduce outside facts.
>
> Produce:
>   - `headline` (≤60 chars, no question mark)
>   - `body` (≤140 chars, the top-line verdict)
>   - `drawer` (≤600 chars, the nuanced explanation. MUST quote at least one `direct_quote` from a bound source verbatim.)
>   - `realism_assessment` ∈ {accurate, mixed, exaggerated, inaccurate}
>   - `expert_attribution[]` from the bound sources
>   - `direct_quotes[]` verbatim
>   - `grounding_type` ∈ {named_expert, generalized_source_supported}
>
> Constraints:
>   - If no named expert in the bound sources, `grounding_type = generalized_source_supported` — the drawer must cite a primary statute or peer-reviewed source, not prose a conclusion.
>   - Do NOT reference sources not in the bound set.
>   - Do NOT invent expert names, titles, or firm names.

### 4.8 Stage 8 — Anti-hallucination validator

Runs on every generated prompt. Rejects if:
1. `expert_attribution[].name` not in Title Source Bank.
2. Any `direct_quotes[]` entry not string-matched (≥0.95) against a Title Source Bank quote.
3. `source_citations[].url` not in Title Source Bank.
4. `drawer` contains a quoted sentence (`"..."`) that isn't in `direct_quotes[]`.
5. `grounding_type = named_expert` but `expert_attribution[]` empty.
6. `realism_assessment` not in the enum.
7. Prompt makes a claim beyond what bound sources support (LLM-judge entailment check).

Rejected prompts go back to Stage 7 with validator notes; after 2 regeneration attempts, the prompt is dropped or queued for HITL-authored rewrite.

### 4.9 Stage 9 — HITL review

Even after validator passes, every realism prompt requires HITL approval before it can surface on a client. This is a non-negotiable gate for launch. Reviewer actions: `approve`, `edit`, `reject`, `escalate_to_legal`.

Escalation triggers:
- Any `realism_assessment = inaccurate` tagged against a named profession (defamation risk if framed as "lawyers do X wrong").
- Any source with named individuals outside the source class they're claimed to represent.
- Moderation-flagged scenes (severity > low).

### 4.10 Stage 10 — Emit

Final prompt written to the SceneSense prompt store using the realism extension of `prompt-output.md`. Indexed by `(title_id, scene_index, primitive=how_real_is_it, domain)`.

## 5. Worked example — *The Devil's Advocate* (scenes 2, 4, 7)

Using the VLM output at `data/samples/The_Devils_Advocate.json`. Source bank follows what you surfaced in your example.

### Scene 2 (`00:00:45–00:02:55`) — Barbara's direct testimony

VLM evidence: `themes = ["Sexual abuse", "Trauma", "Legal proceedings", "Testimony"]`; dialogue includes the prosecutor's leading "And after you told them what he had done to you, they told you what he had done to them! Isn't that true?"

**Extracted claim:** "Leading questions by the prosecutor on direct examination of a minor are standard practice."

**Bound sources:** no direct named-expert reaction to *this specific moment* in your Source Bank. `grounding_type = generalized_source_supported`. Cite Federal Rules of Evidence 611(c) (leading questions generally not allowed on direct but permitted with child witnesses under court discretion).

**Emitted prompt (draft):**
- `headline`: "Can a prosecutor lead a child witness like that?"
- `body`: Mixed — courts often allow leading questions with child witnesses, but at judicial discretion.
- `drawer`: "Under Federal Rule of Evidence 611(c), leading questions are generally disallowed on direct examination, but courts routinely make exceptions for child witnesses where a leading form is necessary to develop testimony. The rule itself does not automatically permit the prosecutor's approach here — it depends on judicial discretion."
- `grounding_type`: `generalized_source_supported`
- `confidence_level`: `medium`

### Scene 4 (`00:04:58–00:09:03`) — Lomax's hostile cross-examination

VLM evidence: `key_actions = ["Cross-examining a witness", "Presenting a handwritten note"]`; dialogue: "A man's career... his reputation... his life is on the line! This is not a joke!"

**Extracted claim:** "A defense attorney can conduct hostile, theatrical cross-examination of a minor without judicial intervention."

**Bound source:** Kaufman & Lynd, *2 Attorneys React to Famous Movie Scenes #2*, YouTube, 06:15–09:25. Direct quote: *"Even if the other attorney didn't object, the judge would knock that down after 10 seconds of that... 'Hold on Counsel, approach. You ot continue that line of diatribe in front of this jury. And if you do, I'll declare a mistrial.'"*

**Emitted prompt (draft):**
- `headline`: "Would a real judge allow that cross-examination?"
- `body`: Inaccurate — the judge would almost certainly intervene within seconds.
- `drawer`: "Practicing trial attorneys Jeff Kaufman and Craig Lynd reviewed this scene and said a real judge 'would knock that down after 10 seconds of that' and threaten a mistrial if the attorney didn't stop. Aggressive badgering of a child witness triggers a sidebar, not cinematic silence."
- `realism_assessment`: `inaccurate`
- `expert_attribution`: Kaufman & Lynd, practicing trial attorneys
- `direct_quotes`: [the verbatim above]
- `grounding_type`: `named_expert`
- `confidence_level`: `high`

### Scene 7 (`00:14:56–00:17:20`) — Jury selection

VLM evidence: `themes = ["Legal strategy", "Intuition vs. Experience", "Jury selection"]`; dialogue: "He may look like a brother with an attitude to you, but I see a man with a shotgun under his bed..."

**Extracted claim:** "An elite trial lawyer can instantly read jurors from surface cues (jewelry, hair, demeanor)."

**Bound sources:** Kaufman & Lynd (YouTube) — call the speed dramatization but the underlying practice accurate. *Law & Literature Journal* cited source in your example has no named author, so per §4.4 it demotes to `generalized_source_supported` unless a named scholar can be resolved from the article's byline.

**Emitted prompt (draft):**
- `headline`: "Can you really pick a jury by looking at them?"
- `body`: Mixed — the speed is Hollywood, but the underlying method is real.
- `drawer`: "Trial attorneys Kaufman and Lynd confirm that voir dire does rely heavily on rapid demographic and body-language reads — 'trial lawyers have limited time and data, so they rely on split-second demographic profiling.' The film compresses a real skill into a near-supernatural one."
- `realism_assessment`: `mixed`
- `expert_attribution`: Kaufman & Lynd
- `grounding_type`: `named_expert`
- `confidence_level`: `high`

## 6. Open design decisions

1. **Source-bank refresh cadence.** YouTube videos get taken down. Rebuild per title every N months, or on-read revalidation?
2. **Multi-language.** English-only at MVP; when/how we extend to other markets.
3. **Named-expert source drift.** If Kaufman leaves the firm, does our attribution need a temporal snapshot? Proposal: `verified_at` timestamp.
4. **"Unspecified expert" handling.** Your example marked *Law & Literature Journal* as "Unspecified Legal Scholars | Academic." Per §4.4 this should demote. Confirm the policy.
5. **Competitive advertisers.** A legal-realism prompt next to a LegalZoom ad is fine; next to a different law firm's ad it's fraught. Pipeline must pass realism-prompt context to the competitive-brand exclusion check.
6. **Actor-reference policy.** A prompt that quotes a real attorney discussing *Keanu Reeves' character* is fine. A prompt that uses the actor's name or voice in AI-generated content hits SAG-AFTRA + TN ELVIS Act (see `research/legal-considerations.md` — to be expanded). Proposed rule: never reference actor names in realism prompts; always refer to the character name.

## 7. Dependencies

- Prompt-output schema extension (see `schema/prompt-output.md` — realism fields).
- URL resolver + body-scraper with caching (likely a small utility in `src/scene_sense/enrichment/`).
- Source retrieval (YouTube Data API, web search API — TBD which).
- LLM judge for claim-binding entailment.
- HITL tooling (reuse Adrise CMS or a new review UI — open question per `01-content-intelligence.md`).

## 8. Rollout

- Hackathon phase: build offline pipeline end-to-end on *Devil's Advocate* + 1 medical title + 1 historical title. Target: 10 validated realism prompts per title, 100% manually-audited.
- Post-hackathon: generalize to the hero-title slate (5–10 titles).
- Post-MVP: automated source-bank rebuild, broader domain support, multi-language.
