# Changelog

All notable changes to this project are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.1.0] — 2026-05-11

First production-grade cut: shareable repo with a reproducible demo, unified
CLI, packaging, and smoke tests.

### Added
- Unified `scene-sense` CLI with subcommands: `demo`, `validate`, `tier0`,
  `trivia`, `hriv2`, `facts`, `cast`, `finalize`, `run-all`, `version`.
- Installable package via `pyproject.toml` — `pip install -e .`.
- Packaged Legally Blonde demo bundle — `scene-sense demo` works with no API keys.
- Pure-Python UI-schema contract + `scene-sense validate` for bundles.
- Smoke test suite (`tests/`) covering the demo bundle, schema contract, and CLI.
- Architecture diagrams + reference imagery in `docs/assets/`.
- `docs/archive/` for superseded drafts (v1 HRIT spec, LB realism v1, viral top-25).
- Hand-curated Legally Blonde demo locked:
  - 6 cards in playback order (sceneFact / sceneTrivia / sceneTrivia / actorFact / sceneHRIT / sceneHRIT).
  - All cue points manually verified against the film.
  - Lia's final review comments applied (Fact Check prompt format, Paulette attribution, Coolidge chain simplified).

### Changed
- Consolidated 10 loose `scripts/*.py` into the single `scene-sense` CLI.
  `scripts/run_all.py` remains as a back-compat redirector.
- Pipeline orchestration is now in-process (`cli/run_all_impl.py`) instead of
  shelling out to sibling scripts — faster, cleaner errors.
- README rewritten: positioning, architecture, 60-second demo, card contract,
  repo layout, install matrix, CLI reference.

### Removed
- Stray top-level files: `test_high_res.png`, `split_and_capture.py`.
- `.DS_Store` scatter.
- Unmaintained sibling scripts now subsumed by the CLI.
