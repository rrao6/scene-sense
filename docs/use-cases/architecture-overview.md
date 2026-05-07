# SceneSense — System Architecture

```mermaid
flowchart TB
    VLM[("`**Tubi Moments VLM JSON**
    scenes · cast · dialogue · themes · objects
    wiki-matched trivia · audio-recognized songs`")]

    subgraph INPUT["`**1. Ingest + Domain Detection**`"]
        direction LR
        LOAD["Load scenes"]
        DOMAIN["`Domain classifier
        _legal · historical · medical ·_
        _military · hacking · rom-com_`"]
        ELIG["`Eligibility gate
        skip moderation-flagged scenes
        skip <15s scenes`"]
        LOAD --> DOMAIN --> ELIG
    end
    VLM --> INPUT

    subgraph GEN["`**2. Generation — 5 Parallel Pipelines**`"]
        direction TB

        subgraph T0["`**Tier-0** _(deterministic, 0 API)_`"]
            T0A["Wiki trivia extractor<br/>dedup across scenes<br/>confidence-ranked"]
            T0B["Song ID emitter<br/>audio-rec from VLM"]
            T0C["Celebrity card placeholder<br/>face-rec from VLM"]
        end

        subgraph CE["`**Cast Enrichment**`"]
            CE1["Unique-actor collector<br/>skips top-billed"]
            CE2["Gemini + Google Search<br/>grounding citations only"]
            CE3["Verbatim quote extraction<br/>title-grounding gate"]
        end

        subgraph TR["`**Trivia (MCQ)**`"]
            TR1["Topic proposer<br/>3-4 per scene"]
            TR2["Grounded web search<br/>2 queries per topic"]
            TR3["Fetch + title-ground<br/>cap 3 sources"]
            TR4["MCQ gen + retry loop<br/>distractor overlap ban"]
        end

        subgraph HR["`**How Real Is It? v2**`"]
            HR1["Myth discovery<br/>surprisingly wrong / right / invented"]
            HR2["Tier-S source library<br/>LacusCurtius · Perseus · Cornell Law · ABA"]
            HR3["Grounded web fallback<br/>Tier A/B domains only"]
            HR4["Verbatim anchor match<br/>to primary source"]
        end

        subgraph FA["`**Facts (editorial BTS)**`"]
            FA1["Title-level topic cluster<br/>6-12 topics per title"]
            FA2["Tier A/B source ranking<br/>Variety · HR · NYT · Vulture"]
            FA3["3-5 beat drawer<br/>follow-up chain gen"]
        end
    end
    INPUT --> GEN

    subgraph VAL["`**3. Per-Pipeline Validators** _(at generation, not post-hoc)_`"]
        direction TB
        V1["`**URL provenance**
        only Google Search grounding URLs
        never LLM-emitted URLs`"]
        V2["`**Verbatim anchor match**
        fact_snippet ⊂ fetched body
        answer ⊂ fact_snippet`"]
        V3["`**Cross-source corroboration**
        cast_career → ≥2 domains`"]
        V4["`**Expert gate**
        reject pseudonyms / handles
        2+ capitalized tokens required`"]
        V5["`**Source quality blacklist**
        reject Poshmark · Pinterest · fan wikis
        blogspot · wordpress · facts.net`"]
        V6["`**MCQ option-kind**
        all options same kind
        no character name as distractor
        length variance cap`"]
        V7["`**Retry loop**
        regen on distractor overlap
        banned-list inside prompt`"]
    end
    GEN --> VAL

    subgraph FIN["`**4. Finalizer**`"]
        direction TB
        F1["`**Dedup**
        semantic key: scene + primitive
        + sorted-keyword hash
        cast_enriched overrides tier0`"]
        F2["`**7-Dimension Scorecard**`"]
        F3["`**Verdict logic**
        acc<0.8 ∨ legal<0.8 → reject
        else if overall≥0.8 → approve
        else → needs_edit`"]
        F1 --> F2 --> F3

        subgraph SCORE["`**Scorer dimensions** _(weighted)_`"]
            S1["accuracy ·25%"]
            S2["legal_safety ·20%"]
            S3["prompt_quality ·15%"]
            S4["response_quality ·10%"]
            S5["verbosity ·10%"]
            S6["user_interaction ·10%"]
            S7["monetization_fit ·10%"]
        end
        F2 -.-> SCORE
    end
    VAL --> FIN

    subgraph EVAL["`**5. Deterministic Eval** _(optional, live re-fetch)_`"]
        direction TB
        E1["`Re-fetch every cited URL
        verify title-grounding still holds
        re-match quote verbatim`"]
        E2["`Feeds accuracy score
        overrides generator's self-claim`"]
        E1 --> E2
    end
    FIN --> EVAL

    subgraph OUT["`**6. Client Output**`"]
        direction TB
        UI[("`**ui.json** _(client contract)_
        actorFact · sceneFact
        actorTrivia · sceneTrivia`")]
        CARDS[("`**cards.md** _(HITL review)_
        per-card verdict + issues`")]
        FINAL[("`**final.json** _(full audit)_
        every score · every evidence`")]
        REVIEW[("`**review.json**
        detailed per-card scorecard`")]
    end
    EVAL --> OUT

    style VLM fill:#0f172a,color:#fff,stroke:#64748b,stroke-width:2px
    style INPUT fill:#1e293b,color:#fff
    style GEN fill:#082f49,color:#fff
    style T0 fill:#10b981,color:#000
    style CE fill:#14b8a6,color:#000
    style TR fill:#3b82f6,color:#fff
    style HR fill:#f59e0b,color:#000
    style FA fill:#a855f7,color:#fff
    style VAL fill:#7f1d1d,color:#fff
    style V1 fill:#fca5a5,color:#000
    style V2 fill:#fca5a5,color:#000
    style V3 fill:#fca5a5,color:#000
    style V4 fill:#fca5a5,color:#000
    style V5 fill:#fca5a5,color:#000
    style V6 fill:#fca5a5,color:#000
    style V7 fill:#fca5a5,color:#000
    style FIN fill:#713f12,color:#fff
    style F1 fill:#fde68a,color:#000
    style F2 fill:#fde68a,color:#000
    style F3 fill:#fde68a,color:#000
    style SCORE fill:#422006,color:#fff
    style S1 fill:#fcd34d,color:#000
    style S2 fill:#fcd34d,color:#000
    style S3 fill:#fcd34d,color:#000
    style S4 fill:#fcd34d,color:#000
    style S5 fill:#fcd34d,color:#000
    style S6 fill:#fcd34d,color:#000
    style S7 fill:#fcd34d,color:#000
    style EVAL fill:#164e63,color:#fff
    style E1 fill:#67e8f9,color:#000
    style E2 fill:#67e8f9,color:#000
    style OUT fill:#4c1d95,color:#fff
    style UI fill:#a78bfa,color:#000,stroke-width:3px
    style CARDS fill:#c4b5fd,color:#000
    style FINAL fill:#c4b5fd,color:#000
    style REVIEW fill:#c4b5fd,color:#000
```

---

## How it works (6 layers)

**1 · Ingest + Domain Detection** — Load the VLM JSON, classify primary domain (legal / historical / medical / etc.), gate scenes by duration and moderation severity.

**2 · Generation** — 5 parallel pipelines, each with its own sub-stages:
- **Tier-0** — wiki trivia, songs, celebrity cards from what the VLM already produced. Zero API calls.
- **Cast Enrichment** — unique-actor collection, Google Search grounding, verbatim quote extraction.
- **Trivia** — topic proposer → grounded search → fetch + filter → MCQ generation with retry loop.
- **How Real Is It? v2** — myth discovery → Tier-S curated primary sources (LacusCurtius, Perseus, Cornell Law, ABA) → verbatim anchor match.
- **Facts** — title-level topic clustering → Tier A/B ranked search → 3-5 beat drawer + follow-up chains.

**3 · Per-Pipeline Validators** — 7 hard gates at generation time (not post-hoc):
- URL provenance (never LLM-emitted)
- Verbatim anchor match (quote/fact in live body)
- Cross-source corroboration (cast_career needs 2 domains)
- Expert gate (reject pseudonyms)
- Source quality blacklist (Poshmark, Pinterest, blogspot, facts.net)
- MCQ option-kind (character name can't be distractor; length parity; same kind)
- Retry loop (regen on distractor overlap with banned-list in prompt)

**4 · Finalizer** — semantic dedup across primitives (cast_enriched beats Tier-0 placeholder), 7-dimension weighted scorecard (accuracy 25 · legal 20 · prompt_quality 15 · response_quality 10 · verbosity 10 · UX 10 · monetization 10), verdict logic: `accuracy<0.8 ∨ legal<0.8 → reject; overall≥0.8 → approve; else needs_edit`.

**5 · Deterministic Eval** *(optional)* — re-fetches every cited URL at finalize time, re-matches the quote verbatim, overrides the generator's self-claim. Catches cases where a source went 404 or a quote drifted.

**6 · Client Output** — four files:
- `ui.json` — client contract: `actorFact · sceneFact · actorTrivia · sceneTrivia`
- `cards.md` — human HITL review
- `final.json` — full audit (every score, every evidence)
- `review.json` — detailed per-card scorecard

## Example outputs (Gladiator demo)

| Card shape | Source | Example |
|---|---|---|
| **sceneFact** | How Real Is It? | *"Gladiator invented 'Strength and honor' motto"* — cites **Petronius, Satyricon 117** via Perseus Digital Library |
| **sceneFact** | Facts | *"Russell Crowe's Real-Life Battle Scars"* — disintegrating hip, torn Achilles, missing toe cartilage |
| **sceneTrivia** | Trivia | *"Where was the wheat field filmed?"* → **3 km south of Pienza, Terrapille road** |
| **actorTrivia** | Trivia (cast_career) | *"Before Commodus, which film did Joaquin Phoenix star in?"* → **8mm (1999)** |
| **actorFact** | Cast Enrichment | *"Joaquin Phoenix — breakthrough as Commodus earned an Oscar nomination"* |
