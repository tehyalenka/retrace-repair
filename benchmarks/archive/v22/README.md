# v2.2 Natural-Failure Recovery

First capture an actual model attempt (not a seeded defect). Record first-attempt passes as baseline evidence. Only verified test failures are replayed into two independent repair conditions, with identical initial response and repository state. Feedback contains failed-test identifiers only. Provider failures are excluded from repair success/failure and retried on resume. The first model capture is made once per case/trial and saved in a separate trace file.

Run from the repository root:

```bash
PYTHONPATH=src:. python3 -m benchmarks.v22.natural_recovery --mode offline --cases bugfix --repeats 1 --output v22-offline.json
PYTHONPATH=src:. python3 -m benchmarks.v22.natural_recovery --mode live --cases bugfix feature refactor --repeats 2 --cooldown 90 --output v22-live.json
# If paused, rerun the same command with --resume
```

**Privacy:** `*-traces/*.json` and reports contain prompts, generated code and test logs. Do not publish without review. Offline mode is scripted and is not live model evidence. A small sample and only three synthetic repository tasks cannot establish a general performance advantage.
