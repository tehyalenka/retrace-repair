# RETRACE v2.0 Exploratory Pilot Evaluation Report
## Defensive AST Structural Scoring & Invariant Contract Prompting on Enterprise State Machines

**Study Status:** Exploratory Six-Task Pilot (Investigative Diagnosis)  
**Target Fixture Cluster:** 6 Hardest Enterprise Distributed State-Machine Tasks (Fault Tolerance & Sagas)  
**Evaluator Model:** `openai/gpt-oss-120b` (Provider: Groq, Temp=0.0/0.7, Attempts=2, Seed=142)  
**Evidence Sealed Directory:** `research-v2-pilot/` (Cryptographic Evidence Manifest: 17 artifacts, SHA-256 sealed)  
**Baseline Reference:** RETRACE v1.9 Frozen Release (`research-enterprise-30/`)

---

## 1. Executive Summary

In RETRACE v1.9, the 30-task enterprise benchmark revealed a critical vulnerability across all three repair strategies: models frequently produce patches that satisfy visible public tests by implementing shallow workarounds, but fail held-out invariant suites (the *Public-to-Held-Out Generalization Gap*).

For RETRACE v2.0, we explored **Option 1**:
1. **Defensive AST Structural Quality Scorer:** An automated, syntax-tree analysis engine (`score_candidate_defense`) that evaluates candidate patches without running held-out tests. It rewards explicit parameter validation (`isinstance`, boundary checks, rejecting boolean subtypes), transactional atomicity (`try/finally`, rollback handlers), and strict type enforcement, while penalizing swallowed exceptions (`except ...: pass`) and code bloat.
2. **Invariant Contract Prompting:** System and candidate generation prompts augmented with strict defensive programming rules: fail-closed entrypoint validation, state machine conservation (no premature probation resets), atomic reverse saga compensations, and zero swallowed exceptions.

We evaluated these modifications on the **6 hardest distributed state-machine tasks** in the benchmark:
- `enterprise_circuit_breaker`
- `enterprise_saga_coordinator`
- `enterprise_dead_letter_retry`
- `enterprise_cache_stampede_mutex`
- `enterprise_bulkhead_isolation`
- `enterprise_outbox_publisher`

### Central Research Observation:
> The pilot revealed a divergence between visible-test performance and held-out correctness. Task-level failures suggest that structural candidate-ranking heuristics may favor syntactically defensive repairs that violate behavioral contracts. A factorial ablation is required to isolate the contribution of structural scoring and invariant prompting.

### Descriptive Pilot Highlights:
- **Replay Public Verification Pass Rate Jumped to 100% (+33.3 percentage points):** In v1.9, Counterfactual Replay passed visible tests on 4/6 tasks (66.7%). Under v2.0, Replay achieved a perfect 6/6 (100.0%) public pass rate.
- **Novel Invariant Discovery on Mutex Concurrency (`enterprise_cache_stampede_mutex`):** In v1.9, Replay failed both public and held-out tests (`pub=False, held=False`). In v2.0, the AST defensive scorer penalized un-synchronized branches and prioritized a single-flight mutex with atomic double-checked locking, resulting in a **held-out victory (`pub=True, held=True`)**.
- **Overall Held-Out Success Declined (6/18 $\to$ 4/18):** Replay held-out success decreased from 2/6 to 1/6, and feedback decreased from 1/6 to 0/6, indicating that structural heuristics may introduce unintended behavioral biases.
- **Resample Maintained Generalization:** Resample public pass rate improved from 83.3% (5/6) to 100.0% (6/6), maintaining a 50.0% held-out pass rate across the 6 tasks.

---

## 2. Head-to-Head Empirical Comparison (v1.9 Baseline vs. v2.0)

| Task Name | Strategy | v1.9 Public | v1.9 Held-Out | v2.0 Public | v2.0 Held-Out | Status / Impact |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **`enterprise_circuit_breaker`** | Resample | PASS | PASS | PASS | PASS | Maintained full invariant correctness |
| | Feedback | PASS | FAIL | FAIL | FAIL | Feedback regressed on public tests |
| | Replay | PASS | PASS | PASS | FAIL | Passed public; failed heldout on TypeError vs ValueError |
| **`enterprise_saga_coordinator`** | Resample | PASS | FAIL | PASS | FAIL | Maintained public pass; complex multi-stage saga |
| | Feedback | PASS | FAIL | PASS | FAIL | Maintained public pass; heldout invariant unmet |
| | Replay | FAIL | FAIL | PASS | FAIL | **+Public Pass:** Resolved v1.9 replay public failure |
| **`enterprise_dead_letter_retry`** | Resample | PASS | FAIL | PASS | FAIL | Consistent public pass |
| | Feedback | PASS | FAIL | PASS | FAIL | Consistent public pass |
| | Replay | PASS | FAIL | PASS | FAIL | Consistent public pass |
| **`enterprise_cache_stampede_mutex`** | Resample | FAIL | FAIL | PASS | FAIL | **+Public Pass:** Invariant prompt fixed public sync |
| | Feedback | PASS | FAIL | FAIL | FAIL | Feedback regressed on lock contention |
| | Replay | FAIL | FAIL | **PASS** | **PASS** | **★ HELD-OUT VICTORY:** AST scorer selected perfect mutex |
| **`enterprise_bulkhead_isolation`** | Resample | PASS | PASS | PASS | PASS | Maintained full invariant correctness |
| | Feedback | PASS | PASS | FAIL | FAIL | Feedback broke semaphore queue invariant |
| | Replay | PASS | FAIL | PASS | FAIL | Consistent public pass |
| **`enterprise_outbox_publisher`** | Resample | PASS | PASS | PASS | PASS | Maintained full invariant correctness |
| | Feedback | PASS | FAIL | PASS | FAIL | Consistent public pass |
| | Replay | PASS | PASS | PASS | FAIL | Passed public; failed attempt exhaust transition |

---

## 3. Aggregate Performance Across the 6 State-Machine Fixtures

| Strategy | Metric | RETRACE v1.9 Baseline | RETRACE v2.0 Pilot | Delta |
| :--- | :--- | :---: | :---: | :---: |
| **Resample** | Public Pass Rate | 83.3% (5/6) | **100.0%** (6/6) | **+16.7 pp** |
| | Held-Out Pass Rate | 50.0% (3/6) | 50.0% (3/6) | 0.0 pp |
| | Mean Tokens / Task | ~2,750 | 2,921.5 | +6.2% |
| **Feedback** | Public Pass Rate | 100.0% (6/6) | 50.0% (3/6) | -50.0 pp |
| | Held-Out Pass Rate | 16.7% (1/6) | 0.0% (0/6) | -16.7 pp |
| | Mean Tokens / Task | ~3,900 | 4,103.7 | +5.2% |
| **Counterfactual Replay** | Public Pass Rate | 66.7% (4/6) | **100.0%** (6/6) | **+33.3 pp** |
| | Held-Out Pass Rate | 33.3% (2/6) | 16.7% (1/6) | -16.6 pp |
| | Mean Tokens / Task | ~8,200 | 8,665.0 | +5.7% |

---

## 4. In-Depth Case Analysis

### 4.1 The Concurrency Breakthrough: `enterprise_cache_stampede_mutex`
- **Problem:** When multiple threads request an expired cache key simultaneously, naive implementations either allow multiple redundant backend computations (cache stampede) or create deadlock / race conditions.
- **v1.9 Failure:** In v1.9, Replay generated patches that caused deadlocks or failed to synchronize thread handoffs, failing both public and held-out suites.
- **v2.0 Resolution:** 
  The AST defensive quality scorer rewarded:
  - Explicit synchronization guards (`ast.If` checking existing in-flight events).
  - Proper resource cleanup using `finally:` blocks.
  - Non-boolean hashable key validation.
  The selected candidate implemented single-flight request coalescing using `threading.Event`, allowing all threads to await the single computed result. Both public and held-out invariant test suites passed cleanly.

### 4.2 The Precision Trap: `enterprise_circuit_breaker`
- **Public Result:** Succeeded (all 3 public tests passing).
- **Held-Out Failure:** The candidate included comprehensive parameter checking:
  ```python
  if not isinstance(failure_threshold, int) or isinstance(failure_threshold, bool):
      raise TypeError('failure_threshold must be an int')
  ```
  However, the held-out test suite asserted:
  ```python
  with self.assertRaises(ValueError):
      CircuitBreaker(d, failure_threshold=bad)
  ```
- **Takeaway:** The model adhered strictly to defensive principles, but raised `TypeError` rather than `ValueError` for mismatched types. Future iterations of invariant prompting should specify standard library exception conventions or recommend raising `(ValueError, TypeError)`.

---

## 5. Statistical Significance (McNemar Paired Tests, n=6)

Due to the exploratory sample size ($n=6$ tasks), paired non-parametric tests have limited statistical power, but provide exact directional tracking:
- **Resample vs. Feedback:** 3 discordant pairs (Resample-only = 3, Feedback-only = 0), exact two-sided $p = 0.25$ (non-significant at $\alpha=0.05$).
- **Feedback vs. Replay:** 1 discordant pair (Replay-only = 1, Feedback-only = 0), exact two-sided $p = 1.0$.
- **Resample vs. Replay:** 4 discordant pairs (Resample-only = 3, Replay-only = 1), exact two-sided $p = 0.625$.

---

## 6. Recommendations for RETRACE v2.0 Roadmap

1. **Hybrid Selection Policy:** Combine AST defensive scoring with test execution time profiling. Candidates that execute without excessive latency or lock contention should receive additional ranking weight.
2. **Exception Hierarchy Harmonization:** Update the contract prompt to instruct models that parameter validation errors should raise `ValueError` (or subclass thereof), preventing benign `TypeError` rejections on benchmark fixtures.
3. **Multi-Candidate Scaling:** Increasing counterfactual candidate generation from $k=2$ to $k=4$ on state machines is projected to allow the defensive AST scorer to find candidates that satisfy both structural safety and precise benchmark invariants.
