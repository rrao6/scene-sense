# Trivia Pipeline — Architecture

```mermaid
flowchart TD
    VLM[Tubi Moments VLM JSON<br/>scene: themes, cast, actions, dialogue] --> TOPICS

    TOPICS{"`**1. Topic Proposal**
    _Gemini flash_
    3-4 topics per scene`"}
    TOPICS --> |"{topic, category, search_query}"| GROUND

    GROUND{"`**2. Grounded Search**
    _Gemini + Google Search tool_
    2 queries per topic`"}
    GROUND --> |"only URLs from grounding_metadata<br/>never LLM-emitted text"| FETCH

    FETCH{"`**3. Fetch + Filter**
    _requests / YT transcript API_`"}
    FETCH --> |"body text"| TITLE_GATE
    TITLE_GATE{Title-grounding gate<br/>>=50% of title tokens in body?}
    TITLE_GATE -->|no| DROP_SRC[drop source]
    TITLE_GATE -->|yes| MCQ

    MCQ{"`**4. MCQ Generation**
    _Gemini flash_
    headline + question + answer + 3 distractors`"}
    MCQ --> RETRY{Distractors overlap snippet?}
    RETRY -->|yes, attempt 1| MCQ_RETRY["regenerate with banned list"]
    MCQ_RETRY --> VALIDATE
    RETRY -->|no| VALIDATE

    VALIDATE{"`**5. Validator**
    _rule-based, no LLM_`"}
    VALIDATE --> V1{fact_snippet in body?}
    VALIDATE --> V2{answer in fact_snippet?}
    VALIDATE --> V3{no distractor-snippet overlap?}
    VALIDATE --> V4{"cast: person in scene?"}
    VALIDATE --> V5{"cast_career: 2+ domains?"}

    V1 & V2 & V3 & V4 & V5 --> EMIT[("`**Emit**
    trivia.json
    per-scene records`")]
    EMIT --> FINALIZE

    FINALIZE{"`**Finalizer**
    _7-dim scorecard + dedup_`"}
    FINALIZE --> CARDS_MD[cards.md — HITL review]
    FINALIZE --> CARDS_JSON[cards.json — slim]
    FINALIZE --> REVIEW_JSON[review.json — detailed]
    FINALIZE --> FINAL_JSON[final.json — full audit]

    style VLM fill:#1e293b,color:#fff,stroke:#64748b
    style EMIT fill:#7c3aed,color:#fff,stroke:#a78bfa
    style FINALIZE fill:#f59e0b,color:#000,stroke:#fbbf24
    style CARDS_MD fill:#10b981,color:#000,stroke:#34d399
    style TITLE_GATE fill:#fbbf24,color:#000
    style DROP_SRC fill:#ef4444,color:#fff
    style RETRY fill:#fbbf24,color:#000
    style V1 fill:#fbbf24,color:#000
    style V2 fill:#fbbf24,color:#000
    style V3 fill:#fbbf24,color:#000
    style V4 fill:#fbbf24,color:#000
    style V5 fill:#fbbf24,color:#000
```

---

## Emit schema

```mermaid
classDiagram
    class TriviaCard {
        +string prompt_id
        +int scene_index
        +string scene_start_time
        +string headline "<=8 words, viewer hook"
        +string body "question, 8-20 words"
        +string drawer "1-sentence reveal"
        +Option[] options "1 correct + 3 distractors"
        +Citation[] source_citations
        +TriviaMeta trivia_meta
        +Validator validator
    }
    class Option {
        +string id
        +string label
        +bool correct
    }
    class Citation {
        +string type
        +string url
        +string anchor_text
        +string confidence
    }
    class TriviaMeta {
        +string category
        +string fact_snippet "verbatim from source"
        +string source_url
    }
    class Validator {
        +bool passed
        +string[] errors
        +datetime ran_at
    }
    TriviaCard --> Option
    TriviaCard --> Citation
    TriviaCard --> TriviaMeta
    TriviaCard --> Validator
```

---

## Tuning dials

```mermaid
mindmap
  root((Trivia<br/>Pipeline))
    Accuracy
      quote_validator_threshold 0.88
      title_grounding_pct 50%
      cast_min_domains 2
      max_retries 2
    Copy Quality
      MCQ_SYSTEM prompt
      headline max 8 words
      question 8-20 words
      distractor length parity
    Cost / Runtime
      sources_per_topic cap
      skip pass-2 search
      parallel fetch
      flash vs pro model
    Coverage
      scene_limit
      category bias per genre
      topic_count per scene
```

---

## Category taxonomy

```mermaid
flowchart LR
    T[Topic] --> C{Category}
    C --> CC[cast_career]
    C --> PR[production]
    C --> BTS[behind_the_scenes]
    C --> LC[location]
    C --> OP[object_prop]
    C --> MU[music]
    C --> HR[historical_reference]
    C --> EE[easter_egg]
    C --> CM[cameo]

    CC -.->|requires| SCENE_CAST[person in<br/>scene.detected_cast]
    CC -.->|requires| MULTI_SRC[2+ domains]
    HR -.->|requires| GENRE_MATCH[historical/<br/>period film]

    style CC fill:#ef4444,color:#fff
    style HR fill:#f59e0b,color:#000
    style MU fill:#10b981,color:#000
    style BTS fill:#3b82f6,color:#fff
    style LC fill:#10b981,color:#000
    style OP fill:#10b981,color:#000
    style EE fill:#a855f7,color:#fff
    style CM fill:#a855f7,color:#fff
    style PR fill:#3b82f6,color:#fff
```

Red = has accuracy gates · Amber = genre-gated · Green = low-risk · Purple = discovery-heavy

---

## Sibling pipelines

```mermaid
flowchart LR
    VLM[VLM JSON] --> T0
    VLM --> TR
    VLM --> HR
    VLM --> F

    T0["`**Tier-0**
    deterministic,
    no API`"]
    TR["`**Trivia**
    MCQ, grounded,
    retry loop`"]
    HR["`**How Real Is It?**
    expert quotes +
    statute fallback`"]
    F["`**Facts**
    editorial BTS,
    drawer + chains
    _planned_`"]

    T0 --> FIN
    TR --> FIN
    HR --> FIN
    F -.-> FIN

    FIN["`**Finalizer**
    7-dim score
    dedup
    emit 4 files`"]

    FIN --> OUT[("final · review · cards.md · cards.json")]

    style T0 fill:#10b981,color:#000
    style TR fill:#3b82f6,color:#fff
    style HR fill:#f59e0b,color:#000
    style F fill:#94a3b8,color:#000,stroke-dasharray: 5 5
    style FIN fill:#f59e0b,color:#000
```
