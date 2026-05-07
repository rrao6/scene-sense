"""Curated primary-source anchors for historical-epic myth-busting.

These URLs are pre-vetted and stable (LacusCurtius at U. Chicago is plain HTML,
Perseus Digital Library is open-access classical texts). The pipeline uses these
as authoritative counter-sources when the film makes a claim about ancient Rome.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class HistoricalSource:
    era: str  # "ancient_rome" | "medieval" | "ww2" | "vietnam" | "early_america"
    citation: str
    url: str
    summary: str
    relevance_tags: list[str]
    fallback_urls: list[str] | None = None


HISTORICAL_SOURCES: list[HistoricalSource] = [
    # ---------- ancient_rome: arena / gladiators ----------
    HistoricalSource(
        era="ancient_rome",
        citation="Suetonius, Divus Claudius 21.6 (LacusCurtius)",
        url="https://penelope.uchicago.edu/Thayer/E/Roman/Texts/Suetonius/12Caesars/Claudius*.html",
        summary="Records the only attested use of 'Ave Imperator, morituri te salutant' — said by condemned criminals (naumachiarii), not gladiators, at a mock naval battle staged by Claudius on Lake Fucinus in AD 52.",
        relevance_tags=["morituri te salutant", "gladiator salute", "ave imperator", "strength and honor"],
    ),
    HistoricalSource(
        era="ancient_rome",
        citation="Suetonius, Divus Augustus 44 (LacusCurtius)",
        url="https://penelope.uchicago.edu/Thayer/E/Roman/Texts/Suetonius/12Caesars/Augustus*.html",
        summary="Augustus banned women from viewing gladiators except from the upper seats; previously men and women sat together at the games.",
        relevance_tags=["women at games", "women seating", "colosseum seating", "front row women"],
    ),
    HistoricalSource(
        era="ancient_rome",
        citation="Cassius Dio, Roman History 73.22 (LacusCurtius)",
        url="https://penelope.uchicago.edu/Thayer/E/Roman/Texts/Cassius_Dio/73*.html",
        summary="Commodus was strangled on 31 Dec 192 AD in his bath by his wrestling partner Narcissus, after Marcia's poisoning attempt failed — NOT killed in the arena.",
        relevance_tags=["commodus death", "commodus killed", "narcissus", "emperor killed", "commodus strangled"],
    ),
    HistoricalSource(
        era="ancient_rome",
        citation="Cassius Dio, Roman History 72 (LacusCurtius)",
        url="https://penelope.uchicago.edu/Thayer/E/Roman/Texts/Cassius_Dio/72*.html",
        summary="Marcus Aurelius co-elevated Commodus as Augustus in 177 AD — the opposite of rejecting him. He died of natural causes on 17 March 180 AD, probably from the Antonine Plague.",
        relevance_tags=["marcus aurelius death", "commodus succession", "republic restored", "marcus aurelius murdered"],
    ),
    HistoricalSource(
        era="ancient_rome",
        citation="Petronius, Satyricon 117 (Perseus Digital Library)",
        url="https://www.perseus.tufts.edu/hopper/text?doc=Perseus:text:2008.01.0501",
        summary="The only recorded gladiator oath (auctoramentum) was to 'endure to be burned, to be bound, to be beaten, and to be killed by the sword.' No primary source attests to 'strength and honor' or any similar battle cry.",
        relevance_tags=["gladiator oath", "strength and honor", "auctoramentum"],
    ),
    HistoricalSource(
        era="ancient_rome",
        citation="Anthony Corbeill, Nature Embodied (Princeton, 2004) — UVA faculty page",
        url="https://classics.as.virginia.edu/people/profile/amc8w",
        summary="Leading scholar of Roman gesture. 'Pollice verso' (thumbs UP) signalled death; a closed fist with wrapped thumb (pollices premere) meant sparing the gladiator. The popular thumbs-down-for-death interpretation is likely inverted.",
        relevance_tags=["thumbs down", "thumbs up", "pollice verso", "gladiator kill signal"],
    ),
    HistoricalSource(
        era="ancient_rome",
        citation="Kathleen Coleman, James Loeb Professor of Classics, Harvard",
        url="https://classics.fas.harvard.edu/people/kathleen-coleman",
        summary="Chief academic consultant on Gladiator (2000). Asked to be uncredited because her corrections had little impact on the screenplay; published 'The Pedant Goes to Hollywood' on the experience.",
        relevance_tags=["gladiator consultant", "historical advisor", "ridley scott historian"],
    ),
    HistoricalSource(
        era="ancient_rome",
        citation="Commodus, Roman History 72-73 — gladiator matches (LacusCurtius)",
        url="https://penelope.uchicago.edu/Thayer/E/Roman/Texts/Cassius_Dio/73*.html",
        summary="Cassius Dio and an inscription attest that Commodus fought 735 gladiatorial matches — real events, though opponents typically threw their fights and he killed handicapped persons from safety.",
        relevance_tags=["commodus gladiator", "emperor fighting", "735 matches", "commodus arena"],
    ),
    HistoricalSource(
        era="ancient_rome",
        citation="Colosseum — Wikipedia with primary-source citations",
        url="https://en.wikipedia.org/wiki/Colosseum",
        summary="Hypogeum (two-level tunnel network under the arena, with 80 vertical shafts and hydraulic lifts) is archaeologically real; built under Domitian. Capacity ~50,000.",
        relevance_tags=["colosseum hypogeum", "trapdoors", "arena lifts", "underground tunnels"],
    ),
    HistoricalSource(
        era="ancient_rome",
        citation="Stirrup — history",
        url="https://en.wikipedia.org/wiki/Stirrup",
        summary="Stirrups were invented in Jin-dynasty China in the early 4th century AD and reached Europe via the Avars in the late 6th–7th c. AD. Romans had no stirrups; they used a four-horn saddle.",
        relevance_tags=["stirrups", "roman cavalry", "saddle"],
    ),
    HistoricalSource(
        era="ancient_rome",
        citation="Lorica segmentata — armor dating",
        url="https://en.wikipedia.org/wiki/Lorica_segmentata",
        summary="The Imperial Gallic helmets shown on-screen date to c. AD 75; by 180 AD legionaries wore later segmentata and mail (lorica hamata). Minor anachronism of ~100 years.",
        relevance_tags=["roman armor", "legionary", "imperial gallic helmet", "lorica segmentata"],
    ),
    # ---------- medieval (for future Braveheart etc.) ----------
    HistoricalSource(
        era="medieval",
        citation="Kilt — history",
        url="https://en.wikipedia.org/wiki/Kilt",
        summary="The belted great kilt (feileadh mor) appears in historical record in the late 16th century. Depicting it in a 13th-century setting (William Wallace) is ~300 years early.",
        relevance_tags=["kilt", "braveheart", "scottish highlander", "medieval scotland"],
    ),
]


def find_historical_sources(
    era: str | None, claim_text: str, top_k: int = 3
) -> list[HistoricalSource]:
    claim_lower = claim_text.lower()
    scored: list[tuple[int, HistoricalSource]] = []
    for s in HISTORICAL_SOURCES:
        if era and s.era != era:
            continue
        score = 0
        for tag in s.relevance_tags:
            if tag.lower() in claim_lower:
                score += 3
            else:
                for w in tag.lower().split():
                    if len(w) >= 5 and w in claim_lower:
                        score += 1
                        break
        if score > 0:
            scored.append((score, s))
    scored.sort(key=lambda x: -x[0])
    return [s for _, s in scored[:top_k]]
