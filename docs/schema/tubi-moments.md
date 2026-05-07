# Tubi Moments schema (current model output)

**Source model:** `gemini-3.1-pro-preview`
**Reference sample:** `data/samples/Legally_Blonde.json`

This is what the existing Tubi Moments pipeline (owned by Aryan Gupta) emits today. SceneSense consumes this as its primary input and adds its own prompt-generation layer on top.

## Top level

```jsonc
{
  "title": "Legally Blonde",
  "duration_sec": 5761.714,
  "srt_path": "…subtitle.srt",
  "wikipedia": {
    "page_title": "Legally Blonde",
    "page_url": "https://en.wikipedia.org/wiki/Legally_Blonde",
    "fact_count": 105,
    "enrichable": true,
    "reason": null
  },
  "scenes": [ /* see below */ ],
  "token_usage": { "totals": { "input": ..., "output": ..., "total": ... }, "by_modality": { ... }, "vlm": "gemini-3.1-pro-preview" }
}
```

## Per-scene object

```jsonc
{
  "scene_index": 3,
  "scene_type": "opening_credits" | "content" | ...,
  "start_time": "00:03:37.000",
  "end_time":   "00:04:08.000",
  "duration_seconds": 29.0,
  "summary": "Elle tells her sorority sisters that she thinks Warner is going to propose to her tonight.",
  "characters": ["Elle Woods", "Margot", "Serena"],
  "detected_cast": ["Reese Witherspoon", "Jessica Cauffiel", "Alanna Ubach"],
  "songs": [{ "start_time": "...", "end_time": "...", "title": "...", "artist": "...", "source": "audio_recognition" }],
  "source_chunk_index": 0,

  "adproduct_tags": [ /* IAB product tags w/ tier1..3 + confidence */ ],
  "content_tags":   [ /* IAB content tags  w/ tier1..4 + confidence */ ],

  "moderation_tags": {
    "flagged": [],
    "categories": {
      "explicit_nudity": { "severity": "none", "confidence": 1 },
      "graphic_violence": { "severity": "none", "confidence": 1 },
      /* ...15 categories total... */
    }
  },
  "sentiment_tags": [
    { "core-emotion": "anticipation", "sub-emotion": "excitement", "intensity": "high", "confidence": 4 }
  ],

  "content_desc": {
    "clip_title": "Sorority Sisters Discuss Impending Engagement",
    "summary_paragraph": "The scene opens on ...",
    "structured_data": {
      "characters": ["Elle Woods (excited, hopeful)", ...],
      "celebrities": ["Reese Witherspoon", ...],
      "setting": { "location": "...", "time_of_day": "...", "era": "..." },
      "key_objects": [...],
      "key_actions": [...],
      "mood_and_tone": [...],
      "themes_and_concepts": [...],
      "dialogue_highlights": [...],
      "sound_design": [...]
    }
  },

  "trivia": [
    {
      "text": "The production settled on having Elle go to a fictional college called CULA.",
      "section": "Filming",
      "source": "wikipedia",
      "source_title": "Legally Blonde",
      "source_url": "https://en.wikipedia.org/wiki/Legally_Blonde",
      "match_confidence": "high",
      "match_reasoning": "Margot is wearing a teal and orange shirt with CULA printed on it..."
    }
  ],

  "annotation_skipped": true | false,
  "enrichment_skipped": true | false
}
```

## Notes / limitations SceneSense must address

- Trivia today is **wiki-matched only** — limited coverage, no opinion/poll/explainer primitives yet.
- No `cue_points` at the moments level — SceneSense may need to align to chapters/beats for pause-relevance.
- `adproduct_tags` give IAB product categories — useful for advertiser matching but not for generating prompts.
- `moderation_tags` should gate advertiser-eligible prompts (severity > low ⇒ restricted advertiser pool).
- No social/chatter signals — SceneSense layers this in via Sprout Social.
- No "use-case potential" signals — this is the hardest schema gap (see `prds/01-content-intelligence.md` §7).

## Ask for Aryan's team
- Exposed via Databricks table? Or a file drop per title? (Confirm pipe for SceneSense ingestion.)
- Schema evolution plan — will `content_desc.structured_data` remain stable?
- Can we add `cue_points` + `scene_beats` to inform pause-moment ranking?
