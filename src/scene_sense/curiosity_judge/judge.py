"""Curiosity judge — rates pause-screen cards from a viewer's POV.

The judge sees ONLY what a viewer would see: headline, body, answer (if MCQ),
reveal, source domain. No validator state, no internal scoring, no source text.
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..realism.config import RealismConfig
from ..realism.gemini_client import GeminiClient

log = logging.getLogger(__name__)


JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "interestingness": {"type": "integer", "minimum": 1, "maximum": 5,
                            "description": "Would a viewer find this novel and hook-y? (1=boring, 5=must-tap)"},
        "obviousness": {"type": "integer", "minimum": 1, "maximum": 5,
                        "description": "Is the answer already obvious from the scene? (1=not obvious, 5=viewer already knows)"},
        "mainstream_appeal": {"type": "integer", "minimum": 1, "maximum": 5,
                              "description": "Will a general audience care, not just specialists? (1=niche, 5=universal)"},
        "follow_up_pull": {"type": "integer", "minimum": 1, "maximum": 5,
                           "description": "How strongly does this invite tapping again? (1=dead end, 5=rabbit hole)"},
        "verdict": {"type": "string", "enum": ["approve", "approve_with_edit", "reject"]},
        "reasoning": {"type": "string", "description": "One short sentence. Why this verdict."},
        "suggested_edit": {"type": "string", "description": "If approve_with_edit, the specific fix. Else empty."},
    },
    "required": ["interestingness", "obviousness", "mainstream_appeal", "follow_up_pull", "verdict", "reasoning"],
}


JUDGE_SYSTEM = (
    "You are a TV viewer. A movie is playing. You've paused, and a small card has appeared on your "
    "screen. Rate it AS A VIEWER — not as a fact-checker. You do not see any technical validation, "
    "any source URLs, or any scores. You only see what the card would show.\n"
    "\n"
    "RATE 1-5 on four dimensions:\n"
    "- **interestingness**: Does this make me want to lean in? Novel + specific = 5. Generic or boring = 1.\n"
    "- **obviousness**: Is the answer ALREADY OBVIOUS from what I just watched? Viewer sees Chihuahua "
    "  on screen → obviousness=5 (bad). Viewer needs outside info → obviousness=1 (good).\n"
    "- **mainstream_appeal**: Will a general audience care? Famous person/place/brand = 5. Obscure "
    "  costume designer nobody knows = 1.\n"
    "- **follow_up_pull**: Do I want to tap MORE after this? Real-world hook (is it still open? what "
    "  role did he play? how much does it cost?) = 5. Dead-end fact = 1.\n"
    "\n"
    "VERDICTS:\n"
    "- **approve**: strong on all 4. Ship it.\n"
    "- **approve_with_edit**: mostly good but specific fixable issue (bad distractor, too-long "
    "  headline, minor phrasing). Suggest the fix in suggested_edit.\n"
    "- **reject**: obvious answer, obscure subject, or no follow-up hook. Be firm.\n"
    "\n"
    "LIA'S RUBRIC (our senior PM) — follow it:\n"
    "- If the answer is literally in the dialogue that just played: REJECT.\n"
    "- If the answer is visibly on screen (Chihuahua): REJECT.\n"
    "- If the subject isn't famous enough for a general viewer: REJECT (e.g. a costume designer who "
    "  isn't Dior or Chanel, a minor actor known only for this film).\n"
    "- If the card invites a clear, specific follow-up (Is it still open? What role did he play? How "
    "  much does it cost?): APPROVE.\n"
    "- If MCQ options are badly worded or the wrong category: APPROVE_WITH_EDIT with the fix."
)


@dataclass
class Judgment:
    interestingness: int
    obviousness: int  # lower is better
    mainstream_appeal: int
    follow_up_pull: int
    verdict: str  # approve | approve_with_edit | reject
    reasoning: str
    suggested_edit: str = ""

    def composite(self) -> float:
        """Weighted 0-1 composite. Obviousness inverted."""
        return round(
            (self.interestingness / 5) * 0.30
            + ((6 - self.obviousness) / 5) * 0.25
            + (self.mainstream_appeal / 5) * 0.25
            + (self.follow_up_pull / 5) * 0.20,
            3,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "interestingness": self.interestingness,
            "obviousness": self.obviousness,
            "mainstream_appeal": self.mainstream_appeal,
            "follow_up_pull": self.follow_up_pull,
            "composite": self.composite(),
            "verdict": self.verdict,
            "reasoning": self.reasoning,
            "suggested_edit": self.suggested_edit,
        }


def _viewer_view(p: dict[str, Any]) -> str:
    """Strip everything a viewer wouldn't see. Return a plain-text prompt."""
    primitive = p.get("primitive", "")
    lines: list[str] = []
    lines.append(f"Primitive: {primitive}")
    if p.get("headline"):
        lines.append(f"Headline: {p['headline']}")
    if p.get("body"):
        lines.append(f"Text: {p['body']}")
    if p.get("drawer") and p["drawer"] != p.get("body"):
        lines.append(f"Drawer: {p['drawer']}")
    options = p.get("options") or []
    if options:
        lines.append("Options:")
        for o in options:
            mark = "✓" if o.get("correct") else "·"
            lines.append(f"  {mark} {o.get('label','')}")
    if p.get("follow_ups"):
        fu_strs = []
        for f in p["follow_ups"]:
            if isinstance(f, dict) and f.get("headline"):
                fu_strs.append(f["headline"])
            elif isinstance(f, str):
                fu_strs.append(f)
        if fu_strs:
            lines.append("Follow-ups: " + " / ".join(fu_strs[:3]))
    # Scene context — useful for the "is the answer already in the scene?" check
    if p.get("scene_start_time") and p.get("scene_end_time"):
        lines.append(f"Scene: {p['scene_start_time']} - {p['scene_end_time']}")
    return "\n".join(lines)


def judge_card(
    client: GeminiClient,
    cfg: RealismConfig,
    p: dict[str, Any],
    scene_context: dict | None = None,
) -> Judgment | None:
    """Run the curiosity judge on a single card. Returns None on failure."""
    view = _viewer_view(p)
    scene_info = ""
    if scene_context:
        dh = scene_context.get("dialogue_highlights") or []
        if dh:
            scene_info = "\n\nSCENE CONTEXT (what viewer just heard/saw):\n"
            scene_info += "Dialogue: " + " / ".join(f'"{d}"' for d in dh[:4] if d) + "\n"
            if scene_context.get("key_objects"):
                scene_info += "Visible objects: " + ", ".join(scene_context["key_objects"][:5]) + "\n"
            if scene_context.get("characters"):
                scene_info += "Characters: " + ", ".join(scene_context["characters"][:5]) + "\n"

    prompt = (
        "Here is a pause card a viewer would see:\n\n"
        f"{view}\n"
        f"{scene_info}\n"
        "Rate it 1-5 on each dimension, give a verdict, and explain in one sentence. "
        "Remember: the viewer just watched the scene, so if the answer was literally said or "
        "visible, obviousness should be high and verdict should lean reject."
    )
    try:
        resp = client.structured(
            namespace="curiosity_judge",
            prompt=prompt,
            response_schema=JUDGE_SCHEMA,
            system_instruction=JUDGE_SYSTEM,
            temperature=0.2,
            model=client.cfg.gemini_model_fast,
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("curiosity_judge: call failed: %s", exc)
        return None
    if not resp:
        return None
    try:
        return Judgment(
            interestingness=int(resp["interestingness"]),
            obviousness=int(resp["obviousness"]),
            mainstream_appeal=int(resp["mainstream_appeal"]),
            follow_up_pull=int(resp["follow_up_pull"]),
            verdict=str(resp["verdict"]),
            reasoning=str(resp.get("reasoning", "")),
            suggested_edit=str(resp.get("suggested_edit", "")),
        )
    except (KeyError, ValueError) as exc:
        log.warning("curiosity_judge: parse failed: %s", exc)
        return None
