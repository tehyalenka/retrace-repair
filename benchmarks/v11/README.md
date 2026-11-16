# CodePilot-X v1.1 advanced benchmark

Three new, separate fixtures: cancellation idempotency across modules, atomic batch transfers, and Unicode-aware backwards-compatible search. Independent tests live in `hidden/` and are passed to the agent as verification only after it proposes edits. These are harder *designed* tasks, not a standardized external benchmark. No task is guaranteed to require a retry.

Run from project root (configured API key required):

```bash
python3 benchmarks/v11/evaluate.py --case all --attempts 1 --output benchmark-v11-one.json
python3 benchmarks/v11/evaluate.py --case all --attempts 3 --output benchmark-v11-three.json
```

Compare success and recovery, but note that separate LLM runs are not paired identical outputs. Tests execute trusted Python code in a temporary copy, **not an OS sandbox**. No live API calls are made by offline regression tests.
