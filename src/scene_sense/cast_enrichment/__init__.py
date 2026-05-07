"""Cast enrichment: turn VLM-detected celebrities into real actorFact cards.

The tier0 cast primitive only says "X appears in this scene. Learn more about their other roles."
That gets suppressed from the UI as placeholder text. This pipeline generates genuinely
interesting one-liner facts about each detected actor, cached per-actor (not per-scene).

Flow:
  1. Collect unique actors across a title's scenes
  2. For each actor: grounded search + extract 1-2 verbatim fact sentences about their career
  3. Emit rich actorFact prompts (one per actor, keyed to their most-featured scene)
"""
