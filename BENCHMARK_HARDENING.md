# RETRACE benchmark hardening (offline)

This change adds tests and a benchmark audit, **not agent functionality**. It makes no provider calls and does not add experimental arms. Run only against trusted fixtures: the verifier executes repository code and is **not a security sandbox**.

## Run

From the repository root, with the project's Python environment active:

```sh
PYTHONPATH=src:. python -m unittest tests.test_benchmark_hardening -v
PYTHONPATH=src:. python -m benchmarks.v18.hardening --output benchmark-hardening-results.json
```

The audit copies each of the 15 reference solutions to a temporary directory, confirms that both public and held-out verifiers pass, and then replaces the first encountered nonempty `return` expression with `return None`. It runs both verifiers again and writes task-level results to JSON. Original solutions are never modified. A successful mutation kill indicates verifier sensitivity to **this specific mutation**, not comprehensive coverage or agent repair success.

## Observed result (2026-11-17, offline)

- 15/15 reference solutions passed both verifier suites.
- Public verifier killed 14/15 semantic mutants.
- Held-out verifier killed 15/15 semantic mutants.
- Both killed 14/15; no mutant survived both suites.
- **refactor_sort**: the public verifier missed the injected fault, while held-out tests detected it. This is a concrete public-test coverage gap, not a RETRACE repair failure.
- 5/5 new hardening tests passed.

## Limitations and next validation gates

1. The mutation operator is deliberately narrow (one first-return replacement per fixture). Expand *test inputs and mutation operators* before claiming strong mutation adequacy.
2. All tasks are small synthetic fixtures with related public and held-out test authorship. Independently sourced real-world bugs and independently authored tests are still required.
3. The existing scripted first repair attempt does not establish recovery from natural model-generated mistakes.
4. Full live three-arm comparisons require a configured model provider, matched budgets, completed repetitions, and uncertainty intervals. This audit does not run them or claim a winner.
5. Full repository test discovery was not certified by this run; use isolated per-module runs and time budgets to investigate slow/hanging tests.
6. The execution harness is not a security boundary. Do not run arbitrary downloaded repositories without an external sandbox.
