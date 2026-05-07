"""Facts pipeline — editorial BTS cards with depth + follow-up chains.

Title-agnostic: works on any title that has a Tubi Moments VLM JSON.

Flow:
  1. Topic clustering: group scenes into title-level BTS topics (bootcamp arc, casting arc,
     fashion arc). Topics span multiple scenes; one Fact card per topic, not per scene.
  2. Tiered source discovery: IMDb trivia API, Wikipedia BTS sections, reputable
     entertainment press (Variety, Hollywood Reporter, Ringer oral histories, Vulture),
     interview archives. Grounded search never trusts LLM-emitted URLs.
  3. Fetch + title-grounding gate (same as trivia).
  4. Beat extraction: each topic yields 3-5 narrative beats (named person + specific detail).
  5. Card assembly: 1 short hook + 3-5 drawer beats + 2-3 follow-up chip references.
  6. Validator: every beat must have a cited source; named-people and numbers must appear verbatim.
"""
