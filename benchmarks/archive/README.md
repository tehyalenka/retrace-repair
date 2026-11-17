# Historical Benchmark Archive

This archive preserves the historical iterations and exploratory testbeds developed during the evolution of the Retrace evaluation infrastructure.

## Active Benchmark Suite

The active, supported benchmark suite is located in **[`benchmarks/v18/`](../v18)**:
- **`task_suite_runner.py`**: Full 22-task evaluation runner (15 synthetic + 7 enterprise).
- **`checkpointed_three_arm.py`**: Three-arm paired comparison (`resample`, `feedback`, `counterfactual`) from identical initial failure snapshots.
- **`leakage_resistant.py`**: Independent public vs. held-out test harness preventing test leakage.
- **`hardening.py`**: Multi-operator semantic mutation audit.
- **`research_gate.py`**: Automated gate requiring both public and held-out verifier satisfaction before claiming repair.

---

## Historical Version Index

| Iteration | Description | Historical Purpose |
|-----------|-------------|--------------------|
| **`v09`** | Initial Single-File Repair Baseline | Early exploratory loop for single-file syntax and unit test fixes. |
| **`v11`** | Retrieval & JSON Mode Exploration | Evaluated prompt formatting and lexical vs. AST-guided file retrieval. |
| **`v15`** | Dependency Retrieval Benchmark | Introduced multi-file dependency graph retrieval comparison against lexical search. |
| **`v16`** | Offline Scripted Repair Loop | Introduced deterministic offline fixtures and mock provider replay. |
| **`v19`** | Seeded Stochastic Repair | Initial experiments with prompt perturbation and randomized seeds. |
| **`v20`** | Rigorous Multi-Seed Evaluation | Multi-seed stability trials evaluating repair variance. |
| **`v21`** | Reliable Repair Integration | Early verifier boundary checks and timeout enforcement. |
| **`v22`** | Natural Recovery Checkpointing | Captured natural model mistakes and checkpointed state before repair. |
| **`v23`** | Verifier Audit & False-Positive Hardening | Identified empty-suite and all-skipped verifier vulnerabilities. |
| **`v25`** | Challenging Multi-Step Recovery | Multi-step bugfix tasks requiring chained edits across classes. |
| **`v27`** | Multi-File Budget & Request Accounting | Introduced durable HTTP request reservation budgets and atomic resumption. |
| **`v28`** | Transactional Rollback & Suite Budgets | Verified filesystem rollback on write errors and suite-level token accounting. |
| **`v30`** | Task Selection & Curated Split Audit | Explored difficulty partitioning across algorithmic and enterprise tasks. |

---

## Backward Compatibility

All historical modules in `benchmarks/archive/` remain accessible via Python dynamic resolution through `benchmarks.vXX` or directly as `benchmarks.archive.vXX`.
