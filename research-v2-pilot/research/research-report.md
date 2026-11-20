# RETRACE: Synthetic Three-Arm Repair Benchmark

## Evaluation status

This report covers 45 synthetic tasks and 135 strategy evaluations: 18 completed and 0 pending. Pending evaluations are **not** repair failures.

| Strategy | Completed | Pending | Public pass | Heldout pass | Combined pass | Successful model calls |
|---|---:|---:|---:|---:|---:|---:|
| resample | 6 | 0 | 6 | 3 | 3 | 6 |
| feedback | 6 | 0 | 3 | 0 | 0 | 6 |
| counterfactual_replay | 6 | 0 | 6 | 1 | 1 | 12 |

![Evaluation coverage](evaluation-coverage.svg)

## Resource usage

| Strategy | HTTP known | HTTP unknown | Known HTTP requests | Token-observed evaluations | Observed prompt tokens | Observed completion tokens |
|---|---:|---:|---:|---:|---:|---:|
| resample | 6 | 39 | 13 | 6 | 5755 | 11774 |
| feedback | 6 | 39 | 12 | 6 | 11227 | 13395 |
| counterfactual_replay | 6 | 39 | 27 | 6 | 25538 | 26452 |

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
| enterprise | resample | 6 | 0 | 3 |
| enterprise | feedback | 6 | 0 | 0 |
| enterprise | counterfactual_replay | 6 | 0 | 1 |

## Enterprise architectural cluster breakdown

| Architectural Cluster | Strategy | Completed | Pending | Public pass | Heldout pass | Combined pass |
|---|---|---:|---:|---:|---:|---:|
| transactional_durability | resample | 0 | 0 | 0 | 0 | 0 |
| transactional_durability | feedback | 0 | 0 | 0 | 0 | 0 |
| transactional_durability | counterfactual_replay | 0 | 0 | 0 | 0 | 0 |
| concurrency_crdts | resample | 0 | 0 | 0 | 0 | 0 |
| concurrency_crdts | feedback | 0 | 0 | 0 | 0 | 0 |
| concurrency_crdts | counterfactual_replay | 0 | 0 | 0 | 0 | 0 |
| fault_tolerance_sagas | resample | 6 | 0 | 6 | 3 | 3 |
| fault_tolerance_sagas | feedback | 6 | 0 | 3 | 0 | 0 |
| fault_tolerance_sagas | counterfactual_replay | 6 | 0 | 6 | 1 | 1 |
| multi_tenant_isolation | resample | 0 | 0 | 0 | 0 | 0 |
| multi_tenant_isolation | feedback | 0 | 0 | 0 | 0 | 0 |
| multi_tenant_isolation | counterfactual_replay | 0 | 0 | 0 | 0 | 0 |
| traffic_resource_pools | resample | 0 | 0 | 0 | 0 | 0 |
| traffic_resource_pools | feedback | 0 | 0 | 0 | 0 | 0 |
| traffic_resource_pools | counterfactual_replay | 0 | 0 | 0 | 0 | 0 |
| coordination_consensus | resample | 0 | 0 | 0 | 0 | 0 |
| coordination_consensus | feedback | 0 | 0 | 0 | 0 | 0 |
| coordination_consensus | counterfactual_replay | 0 | 0 | 0 | 0 | 0 |

## Paired comparisons (combined pass)

| Comparison | Eligible pairs | Both pass | First only | Second only | Neither |
|---|---:|---:|---:|---:|---:|
| resample vs feedback | 6 | 0 | 3 | 0 | 3 |
| resample vs counterfactual_replay | 6 | 0 | 3 | 1 | 2 |
| feedback vs counterfactual_replay | 6 | 0 | 0 | 1 | 5 |

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
