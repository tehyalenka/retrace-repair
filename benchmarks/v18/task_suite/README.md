# Synthetic 15-task benchmark suite

Five categories: 4 bugfix, 3 feature, 3 refactor, 3 multifile, 2 regression.
Each task includes a buggy repository, a known-good reference solution, public tests, and separate heldout tests.

**Validate without any model calls:**

```bash
PYTHONPATH=src:. python -m benchmarks.v18.task_suite_runner validate
PYTHONPATH=src:. python -m unittest tests.test_v18_task_suite -v
```

**Run live paired repairs (uses Groq/provider calls and may incur charges):**

```bash
CODEPILOT_MAX_RETRIES=3 CODEPILOT_FORMAT_RETRIES=2 PYTHONPATH=src:. \
python -m benchmarks.v18.task_suite_runner live --output-dir v18-task-suite-results --repetitions 1 --attempts 3
```

The runner writes per-task capture and checkpoint files and a cumulative suite-summary.json. Rerun the exact command to resume finished task checkpoints. It does not support changing task files or provider settings mid-run. The captured first attempt is deterministic, not a naturally occurring model mistake. The reference solutions are for fixture validation only and are not supplied to the agent.

**Limitations:** Synthetic fixtures are small and are not a substitute for externally sourced coding tasks. The initial failed edit is scripted and identical across arms. Model identity, token usage, and cost are not yet recorded. Public and heldout tests are separate, but authorship is shared; they are not a truly independent external benchmark. The runner executes code and is NOT a security sandbox; only use trusted fixtures.
