"""Tier-0: extract prompts directly from OG Tubi Moments JSON.

The OG VLM pipeline has already grounded a lot of facts per scene:
  - `trivia[]`: Wikipedia-matched facts with match_confidence + match_reasoning
  - `songs[]`: audio-recognized title/artist
  - `key_objects`, `celebrities`, `setting` in structured_data
  - `detected_cast`

This module turns those into prompt records WITHOUT any web search.
These are the highest-accuracy prompts in the system because they're
verified at ingest time, not at generation time.
"""
