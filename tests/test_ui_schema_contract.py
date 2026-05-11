"""Validate the schema contract against the packaged demo bundle and a few
hand-crafted edge cases.
"""
from __future__ import annotations

import pytest

from scene_sense.demo import bundle as demo_bundle
from scene_sense.ui_schema.contract import REQUIRED_FIELDS, validate_bundle


def test_packaged_demo_passes_validation():
    report = validate_bundle(demo_bundle.load_demo("legally_blonde"))
    failures = [(c, n) for c, ok, n in report.checks if not ok]
    assert report.ok, f"demo failed validation: {failures}"


def test_missing_title_is_flagged():
    report = validate_bundle({"cards": [{"type": "sceneFact",
                                          "sceneCuepoint": {"sceneIndex": 1,
                                                            "startTime": "00:00:01",
                                                            "endTime": "00:00:05"},
                                          "proactivePrompt": "p",
                                          "factHeader": "h",
                                          "factText": "t",
                                          "followUps": []}]})
    assert not report.ok
    assert any("has title" in c and not ok for c, ok, _ in report.checks)


def test_invalid_type_is_flagged():
    report = validate_bundle({"title": "X",
                              "cards": [{"type": "mystery", "sceneCuepoint": {
                                  "sceneIndex": 0, "startTime": "00:00:01", "endTime": "00:00:05"}}]})
    assert not report.ok


def test_two_correct_trivia_options_is_flagged():
    card = {
        "type": "sceneTrivia",
        "sceneCuepoint": {"sceneIndex": 1, "startTime": "00:00:01", "endTime": "00:00:05"},
        "proactivePrompt": "p",
        "triviaText": "q",
        "triviaOptions": [
            {"id": 0, "isCorrect": True, "triviaOptionText": "a"},
            {"id": 1, "isCorrect": True, "triviaOptionText": "b"},
            {"id": 2, "isCorrect": False, "triviaOptionText": "c"},
            {"id": 3, "isCorrect": False, "triviaOptionText": "d"},
        ],
        "answerText": "a",
        "followUps": [],
    }
    report = validate_bundle({"title": "X", "cards": [card]})
    assert not report.ok
    assert any("exactly one correct option" in c for c, ok, _ in report.checks if not ok)


def test_out_of_order_cards_is_flagged():
    base = {
        "type": "sceneFact",
        "proactivePrompt": "p", "factHeader": "h", "factText": "t", "followUps": [],
    }
    c1 = {**base, "sceneCuepoint": {"sceneIndex": 2, "startTime": "00:10:00", "endTime": "00:10:10"}}
    c2 = {**base, "sceneCuepoint": {"sceneIndex": 1, "startTime": "00:01:00", "endTime": "00:01:10"}}
    report = validate_bundle({"title": "X", "cards": [c1, c2]})
    # Order check should fail even though individual cards are valid
    assert any("sorted by startTime" in c and not ok for c, ok, _ in report.checks)


@pytest.mark.parametrize("ctype", sorted(REQUIRED_FIELDS.keys()))
def test_every_card_type_has_required_fields_declared(ctype):
    assert len(REQUIRED_FIELDS[ctype]) >= 3, f"{ctype} should declare at least a few required fields"
