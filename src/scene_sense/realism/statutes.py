"""Curated primary-source citations used as generalized_source_supported fallbacks.

These are statutes, rules, and regulations that realism prompts can cite when no named-expert
quote is available. Every URL is an authoritative primary source (statute text on an official .gov
or Cornell LII URL, ABA Model Rules text, FDA guidance, etc). These are NOT hallucinated — the
URLs are stable government / law-school / professional-body pages.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Statute:
    domain: str
    citation: str
    url: str
    summary: str  # short description of what the rule actually says
    relevance_tags: list[str]  # informal tags used to match to claims
    fallback_urls: list[str] | None = None  # alternate URLs used at eval time when primary fails


STATUTES: list[Statute] = [
    # ---------- legal ----------
    Statute(
        domain="legal",
        citation="ABA Model Rule 3.3 (Candor Toward the Tribunal)",
        url="https://www.americanbar.org/groups/professional_responsibility/publications/model_rules_of_professional_conduct/rule_3_3_candor_toward_the_tribunal/",
        summary="A lawyer shall not knowingly offer evidence the lawyer knows to be false; if a lawyer discovers false testimony, the lawyer must take reasonable remedial measures, including disclosure.",
        relevance_tags=["perjury", "false testimony", "candor", "suborning", "client lied", "knew client was guilty"],
    ),
    Statute(
        domain="legal",
        citation="ABA Model Rule 1.6 (Confidentiality of Information)",
        url="https://www.americanbar.org/groups/professional_responsibility/publications/model_rules_of_professional_conduct/rule_1_6_confidentiality_of_information/",
        summary="A lawyer shall not reveal information relating to the representation of a client unless the client gives informed consent, subject to enumerated exceptions.",
        relevance_tags=["confidentiality", "attorney-client privilege", "client secret", "admission of guilt"],
    ),
    Statute(
        domain="legal",
        citation="ABA Model Rule 1.1 (Competence)",
        url="https://www.americanbar.org/groups/professional_responsibility/publications/model_rules_of_professional_conduct/rule_1_1_competence/",
        summary="A lawyer shall provide competent representation, requiring legal knowledge, skill, thoroughness, and preparation reasonably necessary for the representation.",
        relevance_tags=["effective counsel", "competence", "6th amendment", "representation"],
    ),
    Statute(
        domain="legal",
        citation="ABA Model Rule 3.4 (Fairness to Opposing Party and Counsel)",
        url="https://www.americanbar.org/groups/professional_responsibility/publications/model_rules_of_professional_conduct/rule_3_4_fairness_to_opposing_party_and_counsel/",
        summary="A lawyer shall not unlawfully obstruct access to evidence, falsify evidence, or counsel a witness to testify falsely.",
        relevance_tags=["fairness", "evidence", "witness coaching"],
    ),
    Statute(
        domain="legal",
        citation="ABA Model Rule 4.4 (Respect for Rights of Third Persons)",
        url="https://www.americanbar.org/groups/professional_responsibility/publications/model_rules_of_professional_conduct/rule_4_4_respect_for_rights_of_third_persons/",
        summary="A lawyer shall not use means that have no substantial purpose other than to embarrass, delay, or burden a third person, including witnesses.",
        relevance_tags=["badgering", "harassment", "hostile cross-examination", "child witness"],
    ),
    Statute(
        domain="legal",
        citation="Federal Rule of Evidence 611 (Mode and Order of Examining Witnesses)",
        url="https://www.law.cornell.edu/rules/fre/rule_611",
        summary="Rule 611(a) requires the court to exercise reasonable control to protect witnesses from harassment or undue embarrassment. Rule 611(c) generally prohibits leading questions on direct examination, but allows them on cross-examination and when necessary to develop a witness's testimony (commonly applied to child witnesses).",
        relevance_tags=["leading questions", "cross-examination", "child witness", "judicial discretion", "badgering"],
        fallback_urls=[
            "https://www.uscourts.gov/sites/default/files/federal_rules_of_evidence_-_dec_1_2022_0.pdf",
        ],
    ),
    Statute(
        domain="legal",
        citation="6th Amendment — Right to Effective Assistance of Counsel",
        url="https://constitution.congress.gov/browse/essay/amdt6-6-1/ALDE_00013745/",
        summary="The Sixth Amendment guarantees a criminal defendant the right to effective assistance of counsel (Strickland v. Washington, 1984). Even clients whose guilt the attorney suspects are entitled to zealous, competent defense.",
        relevance_tags=["effective counsel", "right to counsel", "representation", "guilty client"],
    ),
    Statute(
        domain="legal",
        citation="Voir Dire — Batson v. Kentucky, 476 U.S. 79 (1986)",
        url="https://supreme.justia.com/cases/federal/us/476/79/",
        summary="Jury selection (voir dire) allows both sides to question prospective jurors. Batson prohibits peremptory strikes based on race; strikes must be justified by a race-neutral explanation when challenged.",
        relevance_tags=["jury selection", "voir dire", "peremptory strike", "reading jurors"],
    ),
    Statute(
        domain="legal",
        citation="Contempt of Court (Cornell LII)",
        url="https://www.law.cornell.edu/wex/contempt_of_court",
        summary="Contempt of court is any act that disregards the authority of the court. Judges may impose sanctions — including fines or imprisonment — for disruptive courtroom behavior. Gallery outbursts during trial can be summarily punished at the judge's discretion.",
        relevance_tags=["contempt", "gallery outburst", "courtroom disruption", "judicial sanction"],
    ),
    Statute(
        domain="legal",
        citation="Federal Rule of Evidence 404 (Character Evidence)",
        url="https://www.law.cornell.edu/rules/fre/rule_404",
        summary="Evidence of a person's character or character trait is generally not admissible to prove conduct on a particular occasion. Prior bad acts may be admissible for other purposes (motive, opportunity, intent).",
        relevance_tags=["character evidence", "prior bad acts", "MIMIC", "prejudicial"],
    ),
    # ---------- medical ----------
    Statute(
        domain="medical",
        citation="AMA Principles of Medical Ethics",
        url="https://code-medical-ethics.ama-assn.org/principles",
        summary="Physicians shall uphold standards of professionalism, respect patient autonomy, and maintain confidentiality within the constraints of the law.",
        relevance_tags=["patient autonomy", "informed consent", "confidentiality", "HIPAA"],
    ),
    Statute(
        domain="medical",
        citation="HIPAA Privacy Rule (45 CFR Part 164)",
        url="https://www.hhs.gov/hipaa/for-professionals/privacy/index.html",
        summary="Covered entities may not use or disclose protected health information without patient authorization, except as expressly permitted by the rule.",
        relevance_tags=["patient privacy", "medical records", "disclosure"],
    ),
    # ---------- financial ----------
    Statute(
        domain="financial",
        citation="SEC Rule 10b-5 (Securities Exchange Act)",
        url="https://www.law.cornell.edu/cfr/text/17/240.10b-5",
        summary="It is unlawful to employ any device, scheme, or artifice to defraud, or to make any untrue statement of a material fact, in connection with the purchase or sale of any security.",
        relevance_tags=["insider trading", "securities fraud", "material misstatement"],
    ),
]


def find_relevant_statutes(domain: str, claim_text: str, top_k: int = 3) -> list[Statute]:
    """Dumb tag-overlap match — returns the top-k statutes relevant to the claim."""
    claim_lower = claim_text.lower()
    scored: list[tuple[int, Statute]] = []
    for s in STATUTES:
        if s.domain != domain:
            continue
        score = 0
        for tag in s.relevance_tags:
            if tag.lower() in claim_lower:
                score += 2
            else:
                # partial keyword overlap
                for w in tag.lower().split():
                    if len(w) >= 5 and w in claim_lower:
                        score += 1
                        break
        if score > 0:
            scored.append((score, s))
    scored.sort(key=lambda x: -x[0])
    return [s for _, s in scored[:top_k]]
