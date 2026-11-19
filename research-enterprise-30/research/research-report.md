# RETRACE: Synthetic Three-Arm Repair Benchmark

## Evaluation status

This report covers 45 synthetic tasks and 135 strategy evaluations: 90 completed and 0 pending. Pending evaluations are **not** repair failures.

| Strategy | Completed | Pending | Public pass | Heldout pass | Combined pass | Successful model calls |
|---|---:|---:|---:|---:|---:|---:|
| resample | 30 | 0 | 22 | 13 | 13 | 31 |
| feedback | 30 | 0 | 25 | 13 | 13 | 32 |
| counterfactual_replay | 30 | 0 | 25 | 14 | 14 | 57 |

![Evaluation coverage](evaluation-coverage.svg)

## Resource usage

| Strategy | HTTP known | HTTP unknown | Known HTTP requests | Token-observed evaluations | Observed prompt tokens | Observed completion tokens |
|---|---:|---:|---:|---:|---:|---:|
| resample | 30 | 15 | 54 | 30 | 31787 | 58461 |
| feedback | 30 | 15 | 61 | 30 | 60570 | 62918 |
| counterfactual_replay | 30 | 15 | 120 | 30 | 114314 | 108566 |

HTTP request counts include durable reservations when available. Reservations conservatively count attempts and do not prove that every request reached the provider.

Observed token counts are not necessarily complete totals, particularly for evaluations resumed from checkpoints. N/A means accounting data is unavailable, not zero.

## Methodology

The three strategies are resampling, standard failure-feedback repair, and counterfactual-guided prompting. Each task begins with a replayed deterministic failed edit. Public test feedback may guide repair; heldout verification is intended for post-repair evaluation. Fixtures are synthetic and not an external benchmark.

Combined pass requires both public and heldout passes. Only completed evaluations are included in pass counts. Paired comparisons include a task/repetition only when both strategies completed.

## Category breakdown

| Category | Strategy | Completed | Pending | Combined pass |
|---|---|---:|---:|---:|
| bugfix | resample | 0 | 0 | 0 |
| bugfix | feedback | 0 | 0 | 0 |
| bugfix | counterfactual_replay | 0 | 0 | 0 |
| feature | resample | 0 | 0 | 0 |
| feature | feedback | 0 | 0 | 0 |
| feature | counterfactual_replay | 0 | 0 | 0 |
| refactor | resample | 0 | 0 | 0 |
| refactor | feedback | 0 | 0 | 0 |
| refactor | counterfactual_replay | 0 | 0 | 0 |
| multifile | resample | 0 | 0 | 0 |
| multifile | feedback | 0 | 0 | 0 |
| multifile | counterfactual_replay | 0 | 0 | 0 |
| regression | resample | 0 | 0 | 0 |
| regression | feedback | 0 | 0 | 0 |
| regression | counterfactual_replay | 0 | 0 | 0 |
| enterprise | resample | 30 | 0 | 13 |
| enterprise | feedback | 30 | 0 | 13 |
| enterprise | counterfactual_replay | 30 | 0 | 14 |

## Enterprise architectural cluster breakdown

| Architectural Cluster | Strategy | Completed | Pending | Public pass | Heldout pass | Combined pass |
|---|---|---:|---:|---:|---:|---:|
| transactional_durability | resample | 6 | 0 | 6 | 2 | 2 |
| transactional_durability | feedback | 6 | 0 | 5 | 3 | 3 |
| transactional_durability | counterfactual_replay | 6 | 0 | 6 | 2 | 2 |
| concurrency_crdts | resample | 5 | 0 | 4 | 3 | 3 |
| concurrency_crdts | feedback | 5 | 0 | 5 | 3 | 3 |
| concurrency_crdts | counterfactual_replay | 5 | 0 | 5 | 3 | 3 |
| fault_tolerance_sagas | resample | 6 | 0 | 5 | 3 | 3 |
| fault_tolerance_sagas | feedback | 6 | 0 | 6 | 1 | 1 |
| fault_tolerance_sagas | counterfactual_replay | 6 | 0 | 4 | 2 | 2 |
| multi_tenant_isolation | resample | 5 | 0 | 3 | 2 | 2 |
| multi_tenant_isolation | feedback | 5 | 0 | 5 | 4 | 4 |
| multi_tenant_isolation | counterfactual_replay | 5 | 0 | 4 | 3 | 3 |
| traffic_resource_pools | resample | 5 | 0 | 3 | 2 | 2 |
| traffic_resource_pools | feedback | 5 | 0 | 2 | 0 | 0 |
| traffic_resource_pools | counterfactual_replay | 5 | 0 | 4 | 2 | 2 |
| coordination_consensus | resample | 3 | 0 | 1 | 1 | 1 |
| coordination_consensus | feedback | 3 | 0 | 2 | 2 | 2 |
| coordination_consensus | counterfactual_replay | 3 | 0 | 2 | 2 | 2 |

## Paired comparisons (combined pass)

| Comparison | Eligible pairs | Both pass | First only | Second only | Neither |
|---|---:|---:|---:|---:|---:|
| resample vs feedback | 30 | 8 | 5 | 5 | 12 |
| resample vs counterfactual_replay | 30 | 11 | 2 | 3 | 14 |
| feedback vs counterfactual_replay | 30 | 10 | 3 | 4 | 13 |

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
