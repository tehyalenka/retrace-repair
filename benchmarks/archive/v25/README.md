# v2.5 — audited benchmark instructions

This benchmark corrects only the **checkout** task instructions. The permissions and eventlog task texts are unchanged. All three starting repositories and independent verification scripts are reused unchanged from `benchmarks/v23`.

**Important:** Changing the checkout prompt changes the experiment. Do not merge or directly compare v2.5 results with v2.3 as if they are identically specified tasks. Capture fresh live first attempts for v2.5; never reuse v2.3 live traces. The runner defaults to offline mode and `v25-offline.json` to reduce accidental Groq usage.

Offline validation (no provider calls):

```bash
PYTHONPATH=src:. python3 -m unittest discover -s tests -p 'test_v25_benchmark.py' -v
PYTHONPATH=src:. python3 -m benchmarks.v25.challenging_recovery --mode offline --cases checkout --repeats 1 --cooldown 0 --output v25-offline.json
```

For a later live run, explicitly choose `--mode live --output v25-live.json`. Live mode consumes provider quota.
