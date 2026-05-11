# scripts/

Historical back-compat directory.

All pipelines now ship under the unified `scene-sense` CLI:

```bash
scene-sense --help
scene-sense demo
scene-sense run-all data/samples/Legally_Blonde.json
scene-sense tier0   data/samples/Legally_Blonde.json
scene-sense trivia  data/samples/Legally_Blonde.json --limit 5
scene-sense hriv2   data/samples/Legally_Blonde.json --domain legal
scene-sense facts   data/samples/Legally_Blonde.json --topics 6
scene-sense cast    data/samples/Legally_Blonde.json --max-actors 10
scene-sense finalize --title "Legally Blonde" --moments data/samples/Legally_Blonde.json \
  --outputs data/outputs/legally_blonde.tier0.json
scene-sense validate data/outputs/legally_blonde.demo.json
```

`scripts/run_all.py` is kept as a thin redirector for anyone still invoking the
old path. New work should use `scene-sense run-all` directly.
