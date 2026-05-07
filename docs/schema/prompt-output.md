# SceneSense prompt-output schema (target)

**Status:** Draft — not yet implemented. Goal is a schema the client can render directly.

One title → many scenes → many prompts. Each prompt is one card the client can show.

```jsonc
{
  "title_id": "tubi:legally_blonde",
  "title": "Legally Blonde",
  "scene_index": 14,
  "scene_start_time": "00:14:22.000",
  "scene_end_time": "00:16:05.000",

  "prompt_id": "ss:legally_blonde:14:cast-recognize-chutney",
  "primitive": "cast" | "scene_iq" | "trivia" | "poll" | "explainer" | "send_to_phone" | "shoulder_content",
  "surface": ["ctv_pause", "mobile_pause", "mobile_proactive"],

  "headline": "Recognize her?",
  "body": "Chutney Windham is played by Linda Cardellini.",
  "drawer": "She credits her iconic role in Legally Blonde as allowing her to 'stretch beyond the identity of a canceled show'. She is known most recently for her roles in Mad Men, Dead to Me, and DTF St. Louis on HBO.",
  "options": null,          // trivia/poll only: [{id, label, correct?}]
  "reveal": null,            // trivia/poll only: text or chart shown after selection
  "follow_ups": [            // optional chained prompts
    { "headline": "What else has she been in?", "prompt_id": "ss:…" },
    { "headline": "What is her net worth?",    "prompt_id": "ss:…" }
  ],

  "source_citations": [
    { "type": "wikipedia",  "url": "…", "anchor_text": "…", "confidence": "high" },
    { "type": "internal_kb", "ref": "cast:linda_cardellini" }
  ],

  "quality_scores": {
    "relevance": 0.92,
    "intrigue":  0.78,
    "safety":    1.00,
    "redundancy": 0.08,
    "tone_fit":  0.85
  },

  "hitl": {
    "state": "approved" | "pending" | "rejected" | "edited",
    "reviewer": "ops_user_123",
    "reviewed_at": "2026-05-20T14:02:00Z",
    "notes": "…"
  },

  "monetization": {
    "eligible": true,
    "advertiser_categories": ["beauty", "streaming_services"],
    "excluded_categories":   ["alcohol"],  // from moderation + competitive rules
    "sponsorship_tier": "direct_sold"
  },

  "personalization_hints": {
    "archetypes": ["character_psychology", "fashion", "nostalgia_2000s"],
    "cold_start_weight": 0.7
  },

  "generated_by": {
    "model": "gpt-4o-mini",
    "prompt_version": "v0.3-cast",
    "generated_at": "2026-05-15T03:44:00Z"
  }
}
```

## Realism primitive extension (`primitive = how_real_is_it`)

For realism prompts only, the schema adds:

```jsonc
{
  "realism": {
    "domain": "legal" | "medical" | "historical" | "military" | "book_accuracy" | "stunt_physical" | "science" | "other",
    "assessment": "accurate" | "mixed" | "exaggerated" | "inaccurate",

    "claim_text": "A defense attorney can conduct hostile, theatrical cross-examination of a minor without judicial intervention.",
    "scene_evidence": {
      "dialogue_highlights": ["A man's career... his reputation... his life is on the line!"],
      "key_actions": ["Cross-examining a witness", "Presenting a handwritten note"]
    },

    "expert_attribution": [
      {
        "name": "Jeff Kaufman",
        "source_class": "practicing_professional",
        "role": "Trial attorney",
        "firm_or_org": "Kaufman & Lynd",
        "verified_at": "2026-05-07"
      },
      {
        "name": "Craig Lynd",
        "source_class": "practicing_professional",
        "role": "Trial attorney",
        "firm_or_org": "Kaufman & Lynd",
        "verified_at": "2026-05-07"
      }
    ],

    "direct_quotes": [
      {
        "text": "The judge would knock that down after 10 seconds of that...",
        "speaker": "Craig Lynd",
        "source_url": "https://www.youtube.com/watch?v=0s9RVsVetws",
        "timestamp": "06:15-09:25",
        "validation_hash": "sha256:…"
      }
    ],

    "generalized_sources": [
      {
        "type": "statute" | "regulation" | "peer_reviewed" | "industry_doc",
        "citation": "Federal Rules of Evidence 611(c)",
        "url": "https://www.law.cornell.edu/rules/fre/rule_611",
        "relevance": "Leading questions on direct are generally not allowed; courts may permit exceptions for child witnesses."
      }
    ],

    "grounding_type": "named_expert" | "generalized_source_supported",
    "verifiability": "easily_verifiable" | "requires_expert_interpretation" | "limited_public_sources",
    "confidence_level": "high" | "medium" | "low",

    "validator": {
      "urls_resolved": true,
      "quotes_matched": true,
      "entailment_check_passed": true,
      "ran_at": "2026-05-15T04:02:00Z"
    }
  }
}
```

**Rules enforced by the anti-hallucination validator (see `use-cases/how-real-is-it.md` §4.8):**
- `expert_attribution[].name` must exist in the Title Source Bank.
- Every `direct_quotes[].text` must string-match (≥0.95) against a bank entry.
- `grounding_type = named_expert` requires `expert_attribution[]` non-empty AND `direct_quotes[]` non-empty.
- `grounding_type = generalized_source_supported` requires `generalized_sources[]` non-empty.
- `drawer` text may quote only from `direct_quotes[]`.
- Character names OK in body/drawer; actor names must not appear (SAG-AFTRA / ELVIS Act posture — see `research/legal-considerations.md`).

## Open schema questions

- Where does `cue_points` live — at scene level or prompt level?
- How do we version prompts if we regenerate after a model upgrade?
- Multi-language variants — new prompt IDs vs. `localizations{}` field?
- Do polls with aggregate results need a separate live-state document?
- Realism primitive: does the source bank live in the prompt itself (denormalized, above) or in a separate `source_bank` collection referenced by ID?
