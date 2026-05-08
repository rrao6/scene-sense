"""Subject fame gate.

Given a person/place/brand name, returns a 1-5 fame score. Cached per subject
across runs. Used at topic proposal to veto cards whose subject wouldn't
resonate with a general viewer (e.g. an obscure costume designer, a minor cast
member the audience won't recognize).
"""
