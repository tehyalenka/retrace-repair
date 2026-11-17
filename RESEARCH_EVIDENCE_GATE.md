# RETRACE research evidence gate

This patch adds an **offline** integrity checker for existing three-arm capture/live JSON pairs. It does not modify agent behavior, run untrusted repositories, or consume API credits.

Run:

```bash
PYTHONPATH=src:. python3 -m unittest tests.test_research_gate -v
PYTHONPATH=src:. python3 -m benchmarks.v18.research_gate research-evaluation-v1 research-evaluation-v2
```

The gate rejects missing or duplicate arms, mismatched trace/repository/verifier hashes, unreproduced initial failures, missing held-out execution, public-only success, and inconsistent live-call accounting. It deliberately **does not** certify natural model failures or counterfactual superiority.

## Critical provenance correction

`benchmarks/v18/task_suite_runner.py` constructs a deterministic failed completion and patches `record_replay.agent_module.ask_model` during capture. The capture JSON `mode: live` does not mean the first completion was produced by a live model. Subsequent continuation requests can be live.

## Next scientific experiment

After verifying isolation, collect naturally failed model-generated first attempts without mocking the initial provider call; compare the existing three arms on the same captured failures, matching budgets and independent held-out tests. Report paired per-task outcomes, uncertainty, and all provider blocks. Do not report scripted-capture experiments as natural-failure recovery.

This tool audits only recorded evidence and cannot establish that arm workspaces were isolated at every intermediate step. That needs a separate runtime isolation test.
