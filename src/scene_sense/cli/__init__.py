"""Unified `scene-sense` CLI.

All pipelines are exposed as subcommands of a single entry point. Run
`scene-sense --help` for the full surface.
"""
from __future__ import annotations

from .main import cli

__all__ = ["cli"]
