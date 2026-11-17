# v2.1: Resumable seeded repair benchmark

Apply after v2.0. Run from repository root with `PYTHONPATH=src:.`.

```bash
PYTHONPATH=src:. python3 -m unittest tests.test_v21_reliable_repair -v
PYTHONPATH=src:. python3 -m benchmarks.v21.reliable_repair --mode offline --repeats 2 --output v21-offline.json
export CODEPILOT_JSON_MODE=1
PYTHONPATH=src:. python3 -m benchmarks.v21.reliable_repair --mode live --cases feature --repeats 2 --cooldown 30 --output v21-live-feature.json
# After rate limits clear, run the identical command with --resume:
PYTHONPATH=src:. python3 -m benchmarks.v21.reliable_repair --mode live --cases feature --repeats 2 --cooldown 30 --output v21-live-feature.json --resume
```

A 429 pauses the experiment after the provider's existing retry policy is exhausted. Resuming reruns only the rate-limited arm, preserving completed arms. The output is written atomically after each arm. `fresh_model_calls` counts *successful completions* rather than HTTP attempts; a 429 may involve several attempted HTTP requests. Cooldown applies between arms, not between internal provider retries. Do not use `--continue-on-429` unless deliberately collecting outage data. No live requests occur during offline tests.

**Caution:** An interrupted process between a provider response and atomic save can repeat that arm upon resume. Seeded errors and tiny samples are not evidence of general repair performance. Feedback and resample prompts remain different beyond diagnostic identifiers; this patch does not fix that experimental confound.
