"""UI emit schema — converts internal prompt records into the shape the client UI consumes.

Target shapes (matches the client-team spec):
  - actorFact    { type, sceneCuepoint?, actorImage?, actorName, character?, factText, followUps }
  - sceneFact    { type, sceneCuepoint, factHeader, factText, followUps }
  - actorTrivia  { type, sceneCuepoint?, actorImage?, actorName, character?,
                   triviaText, triviaOptions[], answerText, followUps }
  - sceneTrivia  { type, sceneCuepoint, triviaText, triviaOptions[], answerText, followUps }
  - sceneHRIT    { type, sceneCuepoint, proactivePrompt, title, question, answer, followUps }

Routing:
  - primitive = cast                       -> actorFact
  - primitive = scene_iq                   -> sceneFact
  - primitive = how_real_is_it             -> sceneHRIT (or sceneFact if legacy)
  - primitive = facts                      -> sceneFact (with followUps)
  - primitive = trivia + cast_career/cameo -> actorTrivia
  - primitive = trivia + other categories  -> sceneTrivia

Validation:
  - See `scene_sense.ui_schema.contract.validate_bundle` for the runtime
    schema check, used by the `scene-sense validate` CLI.
"""
from __future__ import annotations

from .contract import CARD_TYPES, REQUIRED_FIELDS, ValidationReport, validate_bundle

__all__ = ["CARD_TYPES", "REQUIRED_FIELDS", "ValidationReport", "validate_bundle"]
