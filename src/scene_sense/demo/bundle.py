"""Copy the hand-curated demo bundle to a user-specified output directory."""
from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

# (source filename inside the package, destination filename)
_BUNDLES = {
    "legally_blonde": [
        ("legally_blonde.demo.json", "legally_blonde.demo.json"),
        ("legally_blonde.demo.md", "legally_blonde.demo.md"),
        ("legally_blonde.ux_walkthrough.md", "legally_blonde.ux_walkthrough.md"),
    ],
}


def available_titles() -> list[str]:
    return sorted(_BUNDLES.keys())


def copy_to(title: str, dest: Path) -> list[tuple[Path, int, int | None]]:
    """Copy the bundle for `title` into `dest`. Returns (path, size, card_count)."""
    if title not in _BUNDLES:
        raise ValueError(
            f"No packaged demo bundle for {title!r}. "
            f"Available: {', '.join(available_titles())}"
        )
    dest.mkdir(parents=True, exist_ok=True)
    files: list[tuple[Path, int, int | None]] = []
    for src_name, dest_name in _BUNDLES[title]:
        source = resources.files("scene_sense.demo").joinpath(src_name)
        payload = source.read_bytes()
        out_path = dest / dest_name
        out_path.write_bytes(payload)
        cards = _card_count(payload) if dest_name.endswith(".json") else None
        files.append((out_path, len(payload), cards))
    return files


def load_demo(title: str = "legally_blonde") -> dict:
    """Return the demo JSON as a parsed dict (for tests / inspection)."""
    if title not in _BUNDLES:
        raise ValueError(f"No packaged demo bundle for {title!r}")
    src_name = _BUNDLES[title][0][0]
    source = resources.files("scene_sense.demo").joinpath(src_name)
    return json.loads(source.read_text(encoding="utf-8"))


def _card_count(payload: bytes) -> int | None:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return None
    cards = data.get("cards")
    return len(cards) if isinstance(cards, list) else None
