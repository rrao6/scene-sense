"""UI emit schema — converts internal prompt records into the shape the client UI consumes.

Target shapes (matches the client-team spec):
  - actorFact { type, sceneCuepoint?, actorImage?, actorName, character?, factText }
  - sceneFact { type, sceneCuepoint, factHeader, factText }
  - actorTrivia { type, sceneCuepoint?, actorImage?, actorName, character?,
                  triviaText, triviaOptions[], answerText }
  - sceneTrivia { type, sceneCuepoint, triviaText, triviaOptions[], answerText }

Routing:
  - primitive = cast                       -> actorFact
  - primitive = scene_iq                   -> sceneFact
  - primitive = how_real_is_it             -> sceneFact
  - primitive = facts                      -> sceneFact (with follow_ups)
  - primitive = trivia + cast_career/cameo -> actorTrivia
  - primitive = trivia + other categories  -> sceneTrivia
"""
