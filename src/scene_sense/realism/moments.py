"""Load Tubi Moments JSON into lightweight scene objects."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _hms_to_seconds(s: str) -> float:
    if not s:
        return 0.0
    try:
        h, m, rest = s.split(":")
        return int(h) * 3600 + int(m) * 60 + float(rest)
    except Exception:
        return 0.0


@dataclass
class Scene:
    scene_index: int
    scene_type: str
    start_time: str
    end_time: str
    duration_s: float
    summary: str
    characters: list[str]
    detected_cast: list[str]
    themes: list[str] = field(default_factory=list)
    key_actions: list[str] = field(default_factory=list)
    key_objects: list[str] = field(default_factory=list)
    dialogue_highlights: list[str] = field(default_factory=list)
    mood_and_tone: list[str] = field(default_factory=list)
    moderation_severity: str = "none"
    content_tags: list[dict[str, Any]] = field(default_factory=list)

    def as_llm_context(self) -> str:
        """Compact textual representation for LLM prompts."""
        bits: list[str] = []
        bits.append(f"[scene_index={self.scene_index}] {self.start_time}–{self.end_time}")
        if self.summary:
            bits.append(f"Summary: {self.summary}")
        if self.themes:
            bits.append("Themes: " + ", ".join(self.themes))
        if self.key_actions:
            bits.append("Actions: " + "; ".join(self.key_actions))
        if self.dialogue_highlights:
            dh = [d for d in self.dialogue_highlights if d]
            if dh:
                bits.append("Dialogue: " + " / ".join(f'"{d}"' for d in dh[:6]))
        if self.characters:
            bits.append("Characters: " + ", ".join(self.characters))
        return "\n".join(bits)


@dataclass
class TitleMoments:
    title: str
    duration_sec: float
    wikipedia: dict[str, Any]
    scenes: list[Scene]

    def content_scenes(self) -> list[Scene]:
        return [s for s in self.scenes if s.scene_type == "content"]


def _max_severity(mod: dict[str, Any] | None) -> str:
    if not mod:
        return "none"
    cats = mod.get("categories") or {}
    order = ["none", "low", "medium", "high"]
    top = 0
    for v in cats.values():
        sev = (v or {}).get("severity") or "none"
        if sev in order:
            top = max(top, order.index(sev))
    return order[top]


def load_moments(path: Path | str) -> TitleMoments:
    p = Path(path)
    data = json.loads(p.read_text())
    raw_scenes = data.get("scenes", [])
    scenes: list[Scene] = []
    for s in raw_scenes:
        cd = (s.get("content_desc") or {}).get("structured_data") or {}
        duration = s.get("duration_seconds")
        if duration is None:
            duration = _hms_to_seconds(s.get("end_time", "")) - _hms_to_seconds(s.get("start_time", ""))
        scenes.append(
            Scene(
                scene_index=s.get("scene_index", 0),
                scene_type=s.get("scene_type", "content"),
                start_time=s.get("start_time", ""),
                end_time=s.get("end_time", ""),
                duration_s=float(duration or 0),
                summary=s.get("summary") or "",
                characters=s.get("characters") or [],
                detected_cast=s.get("detected_cast") or [],
                themes=cd.get("themes_and_concepts") or [],
                key_actions=cd.get("key_actions") or [],
                key_objects=cd.get("key_objects") or [],
                dialogue_highlights=cd.get("dialogue_highlights") or [],
                mood_and_tone=cd.get("mood_and_tone") or [],
                moderation_severity=_max_severity(s.get("moderation_tags")),
                content_tags=s.get("content_tags") or [],
            )
        )
    return TitleMoments(
        title=data.get("title", p.stem),
        duration_sec=float(data.get("duration_sec", 0.0)),
        wikipedia=data.get("wikipedia") or {},
        scenes=scenes,
    )
