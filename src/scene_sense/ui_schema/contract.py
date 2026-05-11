"""Schema contract for client-ready UI bundles.

This is the single source of truth for what a card looks like by the time it
reaches the player. It's intentionally pure Python — no external validator — so
the CLI `scene-sense validate` works in an environment with zero API access.
"""
from __future__ import annotations

from dataclasses import dataclass, field

CARD_TYPES = {"sceneHRIT", "sceneTrivia", "sceneFact", "actorFact"}

# Fields each card type MUST carry.
REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "sceneHRIT":   ("proactivePrompt", "title", "question", "answer", "followUps"),
    "sceneTrivia": ("proactivePrompt", "triviaText", "triviaOptions", "answerText", "followUps"),
    "sceneFact":   ("proactivePrompt", "factHeader", "factText", "followUps"),
    "actorFact":   ("proactivePrompt", "actorName", "character", "factText", "followUps"),
}

CUEPOINT_FIELDS = ("sceneIndex", "startTime", "endTime")


@dataclass
class ValidationReport:
    ok: bool = True
    checks: list[tuple[str, bool, str]] = field(default_factory=list)

    def add(self, check: str, ok: bool, note: str = "") -> None:
        self.checks.append((check, ok, note))
        if not ok:
            self.ok = False


def validate_bundle(data: dict) -> ValidationReport:
    """Validate a client-ready UI bundle.

    Invariants checked:
      - top-level title + cards[] present
      - each card has a valid type
      - each card has a sceneCuepoint with startTime/endTime
      - each card has the required fields for its type
      - sceneTrivia has exactly one correct option
      - cards are sorted by startTime (warning if not)
    """
    report = ValidationReport()

    title = data.get("title")
    report.add("has title", bool(title), f"'{title}'" if title else "")

    cards = data.get("cards")
    report.add("has cards[]", isinstance(cards, list) and len(cards) > 0,
               f"{len(cards)} card(s)" if isinstance(cards, list) else "")
    if not isinstance(cards, list):
        return report

    for i, card in enumerate(cards):
        ctype = card.get("type")
        loc = f"cards[{i}]({ctype})"

        report.add(f"{loc} type valid", ctype in CARD_TYPES,
                   f"got {ctype!r}, expected one of {sorted(CARD_TYPES)}")

        cuepoint = card.get("sceneCuepoint") or {}
        missing_cue = [f for f in CUEPOINT_FIELDS if cuepoint.get(f) in (None, "")]
        report.add(f"{loc} sceneCuepoint complete", not missing_cue,
                   f"missing {missing_cue}" if missing_cue else "")

        required = REQUIRED_FIELDS.get(ctype, ())
        missing_fields = [f for f in required if f not in card]
        report.add(f"{loc} required fields present", not missing_fields,
                   f"missing {missing_fields}" if missing_fields else "")

        if ctype == "sceneTrivia":
            options = card.get("triviaOptions") or []
            correct = [o for o in options if o.get("isCorrect")]
            report.add(f"{loc} exactly one correct option",
                       len(correct) == 1,
                       f"found {len(correct)} correct")

        follow_ups = card.get("followUps")
        report.add(f"{loc} followUps is list", isinstance(follow_ups, list),
                   f"got {type(follow_ups).__name__}")

    # Playback order — cards should be sorted by startTime
    starts = [c.get("sceneCuepoint", {}).get("startTime", "") for c in cards]
    sorted_starts = sorted(starts)
    report.add("cards sorted by startTime", starts == sorted_starts,
               "cards are not in playback order" if starts != sorted_starts else "")

    return report
