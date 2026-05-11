"""Packaged demo bundles.

The Legally Blonde demo is the canonical artifact anyone can reproduce without
API keys. The files live inside the installed package so `scene-sense demo`
works even when the repo checkout isn't available.
"""
from __future__ import annotations

from . import bundle

__all__ = ["bundle"]
