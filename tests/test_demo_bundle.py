"""The packaged demo bundle is the reproducibility contract. These tests must
pass with zero API keys — they exercise the full no-network path that anyone
cloning the repo will hit first.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scene_sense.demo import bundle as demo_bundle


def test_available_titles_lists_legally_blonde():
    assert "legally_blonde" in demo_bundle.available_titles()


def test_load_demo_has_six_cards_in_playback_order():
    data = demo_bundle.load_demo("legally_blonde")
    assert data["title"] == "Legally Blonde"
    assert len(data["cards"]) == 6

    starts = [c["sceneCuepoint"]["startTime"] for c in data["cards"]]
    assert starts == sorted(starts), f"demo cards not in playback order: {starts}"


def test_demo_counts_match_manifest():
    data = demo_bundle.load_demo("legally_blonde")
    counts = data["counts"]
    assert counts["total"] == 6
    assert counts["by_type"] == {
        "sceneHRIT": 2,
        "sceneTrivia": 2,
        "sceneFact": 1,
        "actorFact": 1,
    }


def test_demo_card_types_are_all_valid():
    from scene_sense.ui_schema.contract import CARD_TYPES

    data = demo_bundle.load_demo("legally_blonde")
    for card in data["cards"]:
        assert card["type"] in CARD_TYPES, card


def test_copy_to_writes_three_files(tmp_path: Path):
    out = tmp_path / "demo_out"
    written = demo_bundle.copy_to("legally_blonde", out)

    assert len(written) == 3
    for path, size, _ in written:
        assert path.exists(), path
        assert size > 0

    # The JSON file must survive the copy intact.
    json_path = out / "legally_blonde.demo.json"
    data = json.loads(json_path.read_text())
    assert data["title"] == "Legally Blonde"


def test_copy_to_unknown_title_raises():
    with pytest.raises(ValueError):
        demo_bundle.copy_to("nonexistent", Path("/tmp/noop"))
