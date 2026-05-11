"""Smoke tests for the `scene-sense` CLI — no API keys required.

We only exercise the subcommands that don't touch external services:
  - version
  - demo
  - validate
"""
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from scene_sense import __version__
from scene_sense.cli import cli


def test_cli_help_succeeds():
    result = CliRunner().invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "scene-sense" in result.output.lower() or "Usage" in result.output


def test_version_subcommand_prints_version():
    result = CliRunner().invoke(cli, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_demo_subcommand_writes_bundle(tmp_path: Path):
    out = tmp_path / "demo_output"
    result = CliRunner().invoke(cli, ["demo", "--out", str(out)])
    assert result.exit_code == 0, result.output
    assert (out / "legally_blonde.demo.json").exists()
    assert (out / "legally_blonde.demo.md").exists()
    assert (out / "legally_blonde.ux_walkthrough.md").exists()


def test_validate_subcommand_accepts_demo_bundle(tmp_path: Path):
    # Stage the demo first
    out = tmp_path / "demo_output"
    CliRunner().invoke(cli, ["demo", "--out", str(out)])
    bundle_path = out / "legally_blonde.demo.json"
    assert bundle_path.exists()

    result = CliRunner().invoke(cli, ["validate", str(bundle_path)])
    assert result.exit_code == 0, result.output
    assert "PASS" in result.output


def test_validate_subcommand_rejects_broken_bundle(tmp_path: Path):
    broken = tmp_path / "broken.json"
    broken.write_text(json.dumps({"title": "X", "cards": [{"type": "mystery"}]}))
    result = CliRunner().invoke(cli, ["validate", str(broken)])
    assert result.exit_code == 1
