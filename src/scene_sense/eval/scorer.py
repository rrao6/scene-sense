"""Per-prompt scorer. Each dimension returns (score_0_to_1, issues[]).

Scoring rubric (compact):
  verbosity:        headline <=60, body <=140, drawer <=600  -> 1.0 if all fit; partial otherwise.
  prompt_quality:   scene-specific (references scene props/dialogue/characters) + no generic
                    "often", "typically" hedging without cite + character name present.
  response_quality: trivia options 4, distractors differ from answer, snippet supports answer,
                    distractors not in snippet.
  user_interaction: has headline, body, drawer OR options; dismissable; follow_ups[] list not null.
  legal_safety:     no actor names, no profession-generalization phrasing, no medical advice tone,
                    respects scene.moderation_severity when provided.
  monetization_fit: monetization.eligible consistent with grounding quality; no exclusions mismatch.
  accuracy:         deterministic re-fetch (done in eval_outputs.py); reuse its verdict if provided.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# re-export for clarity
_ = field


# Same banned names list as the realism validator. Extend as the catalog grows.
BANNED_ACTOR_NAMES = re.compile(
    r"\b("
    r"keanu reeves|al pacino|charlize theron|"
    r"reese witherspoon|selma blair|luke wilson|matthew davis|"
    r"linda cardellini|jennifer coolidge|heather matarazzo|"
    r"alanna ubach|jessica cauffiel|victor garber|"
    r"tom hanks|matt damon|tom sizemore"
    r")\b",
    re.IGNORECASE,
)

PROFESSION_GENERALIZATION = re.compile(
    r"\b(lawyers|doctors|attorneys|judges|cops|police|professionals)\b\s+(really|actually|often|frequently|typically)\s+(do|don't|will|won't|never|always)\b",
    re.IGNORECASE,
)

HEDGE_WORDS_STRICT = {
    "typically", "generally", "often", "sometimes", "frequently", "usually",
}


@dataclass
class DimensionScore:
    score: float  # 0.0 – 1.0
    issues: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {"score": round(self.score, 3), "issues": self.issues}


@dataclass
class PromptScorecard:
    accuracy: DimensionScore
    verbosity: DimensionScore
    prompt_quality: DimensionScore
    response_quality: DimensionScore
    user_interaction: DimensionScore
    legal_safety: DimensionScore
    monetization_fit: DimensionScore
    curiosity: DimensionScore = field(default_factory=lambda: DimensionScore(0.5, []))
    curiosity_verdict: str = ""  # "approve" | "approve_with_edit" | "reject" from judge

    def overall(self) -> float:
        # Curiosity now carries the most weight — it's how Lia actually reviews.
        w = {
            "curiosity": 0.30,
            "accuracy": 0.20,
            "legal_safety": 0.15,
            "prompt_quality": 0.10,
            "response_quality": 0.08,
            "verbosity": 0.07,
            "user_interaction": 0.05,
            "monetization_fit": 0.05,
        }
        return round(
            self.curiosity.score * w["curiosity"]
            + self.accuracy.score * w["accuracy"]
            + self.legal_safety.score * w["legal_safety"]
            + self.prompt_quality.score * w["prompt_quality"]
            + self.response_quality.score * w["response_quality"]
            + self.verbosity.score * w["verbosity"]
            + self.user_interaction.score * w["user_interaction"]
            + self.monetization_fit.score * w["monetization_fit"],
            3,
        )

    def verdict(self) -> str:
        # Hard gates: accuracy, legal, or curiosity can veto
        if self.accuracy.score < 0.8 or self.legal_safety.score < 0.8:
            return "reject"
        # Judge verdict — respect "reject" and "approve_with_edit" directly
        if self.curiosity_verdict == "reject":
            return "reject"
        if self.curiosity_verdict == "approve_with_edit":
            return "needs_edit"
        if self.overall() >= 0.75:
            return "approve"
        return "needs_edit"

    def top_issues(self, n: int = 5) -> list[str]:
        allp: list[str] = []
        for name, dim in (
            ("accuracy", self.accuracy),
            ("legal_safety", self.legal_safety),
            ("prompt_quality", self.prompt_quality),
            ("response_quality", self.response_quality),
            ("verbosity", self.verbosity),
            ("user_interaction", self.user_interaction),
            ("monetization_fit", self.monetization_fit),
        ):
            for issue in dim.issues:
                allp.append(f"{name}: {issue}")
        return allp[:n]

    def as_dict(self) -> dict[str, Any]:
        return {
            "overall": self.overall(),
            "verdict": self.verdict(),
            "curiosity": self.curiosity.as_dict(),
            "curiosity_verdict": self.curiosity_verdict,
            "accuracy": self.accuracy.as_dict(),
            "verbosity": self.verbosity.as_dict(),
            "prompt_quality": self.prompt_quality.as_dict(),
            "response_quality": self.response_quality.as_dict(),
            "user_interaction": self.user_interaction.as_dict(),
            "legal_safety": self.legal_safety.as_dict(),
            "monetization_fit": self.monetization_fit.as_dict(),
            "top_issues": self.top_issues(),
        }


# ---------------- dimension scorers ----------------


def score_verbosity(p: dict) -> DimensionScore:
    issues: list[str] = []
    headline = p.get("headline") or ""
    body = p.get("body") or ""
    drawer = p.get("drawer") or ""

    ok = True
    if not headline:
        issues.append("headline_missing")
        ok = False
    elif len(headline) > 70:
        issues.append(f"headline_too_long({len(headline)})")
        ok = False
    if not body:
        issues.append("body_missing")
        ok = False
    elif len(body) > 180:
        issues.append(f"body_too_long({len(body)})")
        ok = False
    # drawer can be empty for trivia
    if drawer and len(drawer) > 700:
        issues.append(f"drawer_too_long({len(drawer)})")
        ok = False
    # very short body is also a smell
    if body and len(body) < 15:
        issues.append("body_too_short")
        ok = False

    # partial scoring
    score = 1.0
    if issues:
        score = max(0.0, 1.0 - 0.15 * len(issues))
    return DimensionScore(score, issues)


def score_prompt_quality(p: dict, scene_context: dict | None = None) -> DimensionScore:
    """Scene-specific + non-generic. scene_context carries characters/key_actions from VLM."""
    issues: list[str] = []
    body = p.get("body") or ""
    drawer = p.get("drawer") or ""
    full = f"{body} {drawer}"

    score = 1.0

    # scene_context match: body or drawer should mention at least one scene-specific anchor
    if scene_context:
        anchors: list[str] = []
        for c in scene_context.get("characters") or []:
            anchors.append(c.lower())
        for a in scene_context.get("key_actions") or []:
            anchors.append(a.lower()[:30])
        full_low = full.lower()
        hits = sum(1 for a in anchors if a and a in full_low)
        if anchors and hits == 0 and p.get("primitive") == "how_real_is_it":
            issues.append("no_scene_anchor_in_prompt")
            score -= 0.25

    # hedge-word pile-up without a cited source is a smell
    hedge_hits = sum(1 for h in HEDGE_WORDS_STRICT if h in full.lower())
    if hedge_hits >= 3 and not p.get("source_citations"):
        issues.append(f"too_many_hedges({hedge_hits})")
        score -= 0.15

    # question-mark in headline (curiosity hook) nice to have for trivia
    if p.get("primitive") == "trivia" and "?" not in (p.get("body") or ""):
        issues.append("trivia_body_missing_question_mark")
        score -= 0.1

    # "Attorney AndrewPrice states" / pseudonym-looking attribution
    if re.search(r"\b(attorney|lawyer|dr\.?)\s+[A-Z][a-z]+[A-Z][a-z]+", full):
        # AndrewPrice-style merged names
        issues.append("suspicious_merged_name")
        score -= 0.2

    return DimensionScore(max(0.0, score), issues)


def score_response_quality(p: dict) -> DimensionScore:
    """Only meaningful for trivia (MCQ). Non-trivia returns perfect."""
    if p.get("primitive") != "trivia":
        return DimensionScore(1.0, [])
    issues: list[str] = []
    score = 1.0
    options = p.get("options") or []
    if len(options) != 4:
        issues.append(f"options_count={len(options)}")
        score -= 0.3
    correct = [o for o in options if o.get("correct")]
    if len(correct) != 1:
        issues.append("not_exactly_one_correct")
        score -= 0.3
        return DimensionScore(max(0.0, score), issues)
    answer = correct[0].get("label", "")
    distractors = [o.get("label", "") for o in options if not o.get("correct")]
    if any(d.strip().lower() == answer.strip().lower() for d in distractors):
        issues.append("distractor_equals_answer")
        score -= 0.3
    # length balance — avoid correct-answer-is-longer tells
    answer_len = len(answer)
    avg_d = sum(len(d) for d in distractors) / max(1, len(distractors))
    if answer_len and avg_d and (answer_len / avg_d > 2 or avg_d / max(1, answer_len) > 2):
        issues.append("answer_length_anomaly")
        score -= 0.15
    return DimensionScore(max(0.0, score), issues)


def score_user_interaction(p: dict) -> DimensionScore:
    issues: list[str] = []
    score = 1.0
    if not p.get("headline"):
        issues.append("no_headline")
        score -= 0.3
    if not p.get("body"):
        issues.append("no_body")
        score -= 0.3
    # trivia must have options; realism/scene_iq must have drawer
    prim = p.get("primitive")
    if prim == "trivia" and not p.get("options"):
        issues.append("trivia_missing_options")
        score -= 0.4
    if prim in ("how_real_is_it", "scene_iq") and not p.get("drawer"):
        issues.append("no_drawer_for_fact_card")
        score -= 0.2
    # follow_ups should be an array (may be empty) — not null
    if p.get("follow_ups") is None:
        issues.append("follow_ups_null")
        score -= 0.1
    return DimensionScore(max(0.0, score), issues)


def score_legal_safety(p: dict, scene_moderation_severity: str = "none") -> DimensionScore:
    issues: list[str] = []
    score = 1.0
    text = " ".join([
        p.get("headline") or "",
        p.get("body") or "",
        p.get("drawer") or "",
        " ".join(o.get("label", "") for o in (p.get("options") or [])),
    ])
    if BANNED_ACTOR_NAMES.search(text):
        # actor names are OK for trivia/cast when the topic is explicitly about the actor.
        # Only flag hard when primitive is how_real_is_it (realism must use character names).
        if p.get("primitive") == "how_real_is_it":
            issues.append("actor_name_in_realism")
            score -= 0.5
        elif p.get("primitive") in ("cast", "facts"):
            # cast + facts primitives legitimately use actor names (BTS requires them)
            pass
        else:
            # trivia in the cast_career category is OK to name the actor
            cat = (p.get("trivia_meta") or {}).get("category", "")
            if cat not in ("cast_career", "cameo"):
                issues.append("actor_name_in_non_cast_context")
                score -= 0.3
    if PROFESSION_GENERALIZATION.search(text):
        issues.append("profession_generalization_defamation_risk")
        score -= 0.4
    if scene_moderation_severity in ("medium", "high") and p.get("monetization", {}).get("eligible"):
        issues.append("sponsored_on_flagged_scene")
        score -= 0.2
    return DimensionScore(max(0.0, score), issues)


def score_monetization_fit(p: dict) -> DimensionScore:
    issues: list[str] = []
    score = 1.0
    mon = p.get("monetization") or {}
    # eligible prompts should have a non-empty advertiser_categories OR tier
    if mon.get("eligible") and not mon.get("sponsorship_tier"):
        issues.append("eligible_without_tier")
        score -= 0.2
    # generalized_source_supported realism should NOT be marked as monetizable at launch —
    # sales needs a named expert to pitch against.
    if p.get("primitive") == "how_real_is_it":
        gt = (p.get("realism") or {}).get("grounding_type")
        if gt == "generalized_source_supported" and mon.get("eligible"):
            issues.append("statute_grounded_marked_monetizable")
            score -= 0.2
    return DimensionScore(max(0.0, score), issues)


def score_accuracy(p: dict, eval_report: dict | None = None) -> DimensionScore:
    """If a deterministic re-fetch report is available, use its verdict. Otherwise trust the
    generator's own validator output."""
    issues: list[str] = []
    if eval_report is not None:
        if eval_report.get("pass"):
            return DimensionScore(1.0, [])
        issues.extend(eval_report.get("notes") or ["eval_harness_rejected"])
        return DimensionScore(0.3, issues)

    # fallback: check the in-generator validator output
    rm = p.get("realism") or {}
    tm = p.get("trivia_meta") or {}
    t0 = p.get("tier0_meta") or {}
    fm = p.get("facts_meta") or {}
    passed = None
    errors: list[str] = []
    if rm:
        passed = rm.get("validator", {}).get("passed")
        errors = rm.get("validator", {}).get("errors") or []
    elif tm:
        passed = tm.get("validator", {}).get("passed")
        errors = tm.get("validator", {}).get("errors") or []
    elif fm:
        passed = fm.get("validator", {}).get("passed")
        errors = fm.get("validator", {}).get("errors") or []
    elif t0:
        passed = t0.get("validator", {}).get("passed")
        errors = t0.get("validator", {}).get("errors") or []

    if passed is True:
        return DimensionScore(1.0, [])
    if passed is False:
        issues.extend(errors)
        return DimensionScore(0.4, issues)
    return DimensionScore(0.7, ["no_validator_output"])


def score_prompt(
    p: dict,
    *,
    scene_context: dict | None = None,
    scene_moderation_severity: str = "none",
    eval_report: dict | None = None,
    curiosity_judgment: dict | None = None,
) -> PromptScorecard:
    curiosity_score = DimensionScore(0.5, [])
    curiosity_verdict = ""
    if curiosity_judgment:
        curiosity_score = DimensionScore(
            score=curiosity_judgment.get("composite", 0.5),
            issues=[curiosity_judgment.get("reasoning", "")] if curiosity_judgment.get("verdict") != "approve" else [],
        )
        curiosity_verdict = curiosity_judgment.get("verdict", "")
    return PromptScorecard(
        accuracy=score_accuracy(p, eval_report=eval_report),
        verbosity=score_verbosity(p),
        prompt_quality=score_prompt_quality(p, scene_context=scene_context),
        response_quality=score_response_quality(p),
        user_interaction=score_user_interaction(p),
        legal_safety=score_legal_safety(p, scene_moderation_severity=scene_moderation_severity),
        monetization_fit=score_monetization_fit(p),
        curiosity=curiosity_score,
        curiosity_verdict=curiosity_verdict,
    )
