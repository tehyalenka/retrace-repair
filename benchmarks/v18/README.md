# v1.8 — Record and replay

Run from the repository root. These traces contain model prompts and generated code: do not commit or publish without reviewing. Only run tests against trusted repositories.

Offline harness check (no API calls):

```bash
python3 benchmarks/v18/record_replay.py capture --mode offline --output v18-offline-trace.json
python3 benchmarks/v18/record_replay.py paired --trace v18-offline-trace.json --offline --output v18-offline-paired.json
```

Live capture (one model implementation attempt, not a full benchmark):

```bash
export CODEPILOT_JSON_MODE=1
python3 benchmarks/v18/record_replay.py capture --mode live --case refactor --output v18-live-trace.json
```

Only if `first_attempt.failure_category` is `test_failure`, continue with paired fresh-model repair:

```bash
python3 benchmarks/v18/record_replay.py paired --trace v18-live-trace.json --output v18-live-paired.json
```

Both arms replay exactly the same initial generated edit and verifier failure. The resample arm retries with the original prompt; feedback arm sees the previous response and test failure. Each arm makes fresh model calls for its subsequent attempts. The script rejects changes in repository Python source, task, or verifier between capture and replay.

**Caveats:** live mode requires a provider API key and may hit HTTP 429. This is a paired single-case demonstration, not a statistically powered experiment. Provider errors can interrupt the script before a report is written; do not interpret them as model failures. A replayed first edit or scripted offline correction is not a fresh autonomous model action.
