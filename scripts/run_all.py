#!/usr/bin/env python3
"""Back-compat wrapper. Prefer: `scene-sense run-all ...`"""
from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from scene_sense.cli.main import cmd_run_all  # noqa: E402

if __name__ == "__main__":
    cmd_run_all.main(prog_name="scripts/run_all.py")
