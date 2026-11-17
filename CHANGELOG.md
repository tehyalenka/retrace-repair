# Changelog

This file records milestones described in the previous README. Historical success figures are **reported observations**, not independently reproduced results.

## Current research prototype

- Local FastAPI/Angular dashboard, artifact/report workflows, and experimental benchmark directories.
- The agent's public Python package and environment variables still use the legacy `codepilot` naming.
- Integrated counterfactual policy replay remains a research goal, not a verified current capability.

## v1.7 — Feedback ablation (documented experiment)

- Compared `single`, `resample`, and `feedback` conditions in offline/live experiment scripts.
- Offline scripted outcomes test harness behavior, not model performance.
- Known design limitation: the resample condition repeats identical prompts at temperature 0; no independent randomization or seeds were established in the original README.
- No comparable live ablation numbers were reported in the previous README.

## v1.6 — Repair diagnostics

- Bounded stage-aware feedback for failed tests and validation.
- Retries begin from the original repository snapshot; provider errors stop retries.
- Added repair attempt/recovery summary fields.

## v1.5 — Controlled retrieval evaluation

- Offline synthetic comparison of lexical and dependency-aware retrieval using small generated repositories.
- Retrieval precision/recall/F1 do not measure real-world repair success.

## v0.8.1 — Generated-test parsing reliability

- Narrow normalization for double-escaped newlines and bounded corrective parsing requests.

## v0.8 — Experimental generated verification

- Optional model-generated `unittest` checks requested before implementation.
- Failed test generation fails closed; generated checks are not independent evidence.

## v0.7 — Multi-file operations

- Supported validated create/modify/delete operations for allowed Python paths.
- Added repository map CLI functionality and best-effort rollback.
- Original README reported 14 passing local tests and a synthetic 9/9 vs 9/9 ceiling result.

## v0.6 and earlier — Synthetic pilots

- v0.6: paired multi-file synthetic benchmark; historical 9/9 in both conditions.
- v0.5.1: 5/5 injected faults detected/repaired in hand-authored checks.
- v0.5: 4/4 completed comparisons; fifth task aborted, no demonstrated improvement.
- v0.4: 20/20 corrected synthetic single-file tasks.
- v0.3: 3/3 hidden-test single-file pilot.

See the relevant scripts and raw artifacts for exact evaluation definitions. Do not generalize these pilot results to real-world performance.
