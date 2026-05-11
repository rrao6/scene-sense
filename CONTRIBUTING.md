# Contributing

This repo is a spec + prototyping workspace. Everything here should stay
runnable, schema-valid, and honest about what it is.

## Dev setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,llm]"
cp .env.example .env     # fill in GEMINI_API_KEY for live generation
pytest
```

`pytest` must pass without any API keys. If you add a test that requires live
credentials, guard it with `pytest.importorskip` or an env-var check so the
no-network path stays green.

## Adding a new pipeline

1. Create `src/scene_sense/<pipeline>/pipeline.py`.
   - Export a single `run_<pipeline>(cfg, moments_path, ...)` function.
   - Return a dataclass summary (scenes processed, prompts generated, output path).
   - Write output to `data/outputs/<slug>.<pipeline>.json`.
2. Add generator records in the **envelope shape** that matches every other
   pipeline: `prompt_id`, `primitive`, `scene_index`, `scene_start_time`,
   `scene_end_time`, `sources[]`, `generated_by`, `hitl`.
3. Wire the CLI: add a subcommand in `src/scene_sense/cli/main.py` and an
   in-process entry in `cli/run_all_impl.py`.
4. Add a smoke test under `tests/` — feed stub records into the pipeline's
   record-shaping helpers and assert the shape is right.

## Adding a new card type

1. Add the type to `CARD_TYPES` + `REQUIRED_FIELDS` in
   `src/scene_sense/ui_schema/contract.py`.
2. Add a routing rule in `src/scene_sense/ui_schema/emit.py` (primitive →
   card type).
3. Extend `tests/test_ui_schema_contract.py` with a positive and negative
   example.
4. Update the "Sample card shapes" section in the README.

## Demo bundle rules

The packaged Legally Blonde demo is a **reviewer-approved artifact**. Any
change to `src/scene_sense/demo/legally_blonde.demo.json` must:

- pass `scene-sense validate`
- keep cards in playback order (`startTime` ascending)
- match the two companion MDs (`legally_blonde.demo.md`,
  `legally_blonde.ux_walkthrough.md`) exactly — no drift between JSON and docs.

If you adjust a card, run:

```bash
scene-sense validate src/scene_sense/demo/legally_blonde.demo.json
# And update the copies in data/outputs/ + docs/research/ in the same PR.
```

## Commit style

- Short, imperative subject line.
- Body explains *why* if the change isn't self-evident from the diff.
- One logical change per commit. Demo-bundle edits are their own commit,
  separate from pipeline edits.

## Codeowners

- **Rahul Rao** — demo bundle, CLI, architecture.
- **Lia Yu** — card QA, demo approval (see `data/eval/lia_gold_lb.json`).
