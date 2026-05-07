"""Trivia primitive generator.

Flow per scene:
  1. Propose candidate trivia topics from VLM structured data (cast, objects, actions, dialogue).
  2. Ground each topic via Google Search (Gemini grounding tool) to get real source URLs.
  3. Fetch sources, extract verbatim fact snippets from the real body text.
  4. Generate an MCQ with plausible distractors; only emit if a source snippet supports the answer.
  5. Validate: answer must be verbatim-present in at least one bound source.
"""
