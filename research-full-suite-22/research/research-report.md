# RETRACE: Synthetic Three-Arm Repair Benchmark

## Evaluation status

This report covers 22 synthetic tasks and 66 strategy evaluations: 66 completed and 0 pending. Pending evaluations are **not** repair failures.

| Strategy | Completed | Pending | Public pass | Heldout pass | Combined pass | Successful model calls |
|---|---:|---:|---:|---:|---:|---:|
| resample | 22 | 0 | 21 | 15 | 15 | 23 |
| feedback | 22 | 0 | 22 | 15 | 15 | 24 |
| counterfactual | 22 | 0 | 21 | 15 | 15 | 22 |

![Evaluation coverage](evaluation-coverage.svg)

## Resource usage

| Strategy | HTTP known | HTTP unknown | Known HTTP requests | Token-observed evaluations | Observed prompt tokens | Observed completion tokens |
|---|---:|---:|---:|---:|---:|---:|
| resample | 22 | 0 | 38 | 22 | 10015 | 14880 |
| feedback | 22 | 0 | 44 | 22 | 25542 | 19398 |
| counterfactual | 22 | 0 | 42 | 22 | 20721 | 12728 |

HTTP request counts include durable reservations when available. Reservations conservatively count attempts and do not prove that every request reached the provider.

Observed token counts are not necessarily complete totals, particularly for evaluations resumed from checkpoints. N/A means accounting data is unavailable, not zero.

## Methodology

The three strategies are resampling, standard failure-feedback repair, and counterfactual-guided prompting. Each task begins with a replayed deterministic failed edit. Public test feedback may guide repair; heldout verification is intended for post-repair evaluation. Fixtures are synthetic and not an external benchmark.

Combined pass requires both public and heldout passes. Only completed evaluations are included in pass counts. Paired comparisons include a task/repetition only when both strategies completed.

## Category breakdown

| Category | Strategy | Completed | Pending | Combined pass |
|---|---|---:|---:|---:|
| bugfix | resample | 4 | 0 | 4 |
| bugfix | feedback | 4 | 0 | 4 |
| bugfix | counterfactual | 4 | 0 | 4 |
| feature | resample | 3 | 0 | 3 |
| feature | feedback | 3 | 0 | 3 |
| feature | counterfactual | 3 | 0 | 3 |
| refactor | resample | 3 | 0 | 3 |
| refactor | feedback | 3 | 0 | 3 |
| refactor | counterfactual | 3 | 0 | 3 |
| multifile | resample | 3 | 0 | 3 |
| multifile | feedback | 3 | 0 | 3 |
| multifile | counterfactual | 3 | 0 | 3 |
| regression | resample | 2 | 0 | 2 |
| regression | feedback | 2 | 0 | 2 |
| regression | counterfactual | 2 | 0 | 2 |

## Paired comparisons (combined pass)

| Comparison | Eligible pairs | Both pass | First only | Second only | Neither |
|---|---:|---:|---:|---:|---:|
| resample vs feedback | 22 | 15 | 0 | 0 | 7 |
| resample vs counterfactual | 22 | 15 | 0 | 0 | 7 |
| feedback vs counterfactual | 22 | 15 | 0 | 0 | 7 |

## Validity and limitations

- 0 completed evaluations contain a recognizable test-discovery infrastructure warning. These outcomes require investigation before any performance claim.
- Provider interruptions and incomplete evaluations may reduce usable paired comparisons. Do not interpret incomplete evaluations as failed repairs.
- A heldout pass alongside a public failure is not counted as combined success.
- Small samples, synthetic fixtures, and a deterministic replayed first failure limit generalizability.
- `live_calls` counts recorded successful model responses, not necessarily all attempted provider requests.
- Never include heldout test contents in model repair prompts.

## Reproduction

```bash
PYTHONPATH=src:. python -m benchmarks.v18.research_report --results-dir v18-task-suite-results --output-dir v18-task-suite-results/research
```

This command reads local JSON only; it does not call an LLM.
