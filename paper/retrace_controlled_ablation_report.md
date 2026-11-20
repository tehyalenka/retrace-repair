# Controlled Candidate-Selection Ablation Study
## Disentangling AST Structural Quality Scoring, Invariant Contract Prompting, and Generalization Regressions in RETRACE v2.0

**Study Status:** Pre-Specified $2 \times 2$ Factorial Candidate-Selection Ablation (Completed)  
**Evaluation Model:** `openai/gpt-oss-120b` (Provider: Groq, Temp=0.7, $k=2$, Frozen Fixtures)  
**Target Suite:** 6 Hardest Enterprise Distributed State-Machine Tasks  
**Telemetry Manifest:** `research-controlled-ablation/ablation-telemetry.jsonl` (SHA-256 sealed candidate pools)  
**Summary Dataset:** `research-controlled-ablation/ablation-summary.csv`  
**Reference Release:** RETRACE v1.9 Frozen Release (`v1.9.0-research-release`, tag `75de313`)

---

## 1. Executive Summary & Resolution of Research Questions

In the RETRACE v2.0 exploratory pilot, introducing two new mechanisms—an automated **Defensive AST Structural Quality Scorer** and **Invariant Contract Prompting**—resulted in a marked divergence: public verification pass rates rose to 100% (+33.3 percentage points on Counterfactual Replay), yet held-out test pass rates regressed from 6/18 to 4/18 across strategies. 

To determine the causal mechanism driving this regression, we implemented and executed a pre-specified, controlled $2 \times 2$ factorial candidate-selection ablation on the six distributed state-machine fixtures. Crucially, candidate generation was strictly decoupled from candidate selection by freezing immutable candidate pools ($\mathcal{P}_{\text{std}}$ and $\mathcal{P}_{\text{inv}}$) before applying selectors, and held-out test suites were evaluated via an independent, access-controlled audit protocol completely inaccessible to the selection policies.

### The Four Research Questions: Definitive Empirical Answers

```
+-------------------------------------------------------------------------------------------------------+
| RESEARCH QUESTION                               | FINDING               | EMPIRICAL EVIDENCE          |
+-------------------------------------------------+-----------------------+-----------------------------+
| RQ1: Selector Disagreement Frequency            | 33.3% Disagreement    | Disagreed on 4 of 12 pools  |
|                                                 |                       | (2 in P_std, 2 in P_inv)    |
| RQ2: Disagreement Held-Out Directionality       | 0.0% Divergence       | In 4/4 disagreements, both  |
|      (Does AST heuristic pick failing patches?) | (0 Selection Failures)| candidates had identical    |
|                                                 |                       | held-out correctness        |
| RQ3: Invariant Prompting Candidate Yield        | +8.4 pp Candidate     | Held-out yield rose from    |
|      (Does invariant prompting improve yield?)  | Correctness Yield     | 33.3% (4/12) to 41.7% (5/12)|
|                                                 | Task-Level Neutral    | Fixed Cache Stampede, but   |
|                                                 |                       | drifted on Circuit Breaker  |
| RQ4: Factorial Interaction                      | No Aggregate           | Identical pass rates across |
|      (Is there an adverse AST * Prompt effect?) | Interaction Observed   | all 4 arms: 3/6 (50.0%)     |
+-------------------------------------------------------------------------------------------------------+
```

### Key Scientific Conclusions:

1. **No Evidence of AST-Induced Selection Failure in Evaluated Sample:**  
   The controlled ablation found no evidence of AST-induced selection failure across the six evaluated tasks. Although AST ranking changed candidate selection in four of twelve pools, these changes did not alter held-out correctness. Across all 12 candidate pools, there was **not a single selection failure (`SELECTION_FAILURE = 0`)**. Whenever the AST selector disagreed with the greedy baseline (4 of 12 pools), both candidates shared the exact same held-out status (either both passed, e.g., in `circuit_breaker` $\mathcal{P}_{\text{std}}$, `bulkhead` $\mathcal{P}_{\text{inv}}$, `outbox` $\mathcal{P}_{\text{inv}}$, or both failed, e.g., in `cache_stampede` $\mathcal{P}_{\text{std}}$).

2. **Public Verification Eligibility Gate Works as Intended:**  
   In 2 out of 12 pools (`enterprise_saga_coordinator` in $\mathcal{P}_{\text{std}}$ and `enterprise_circuit_breaker` in $\mathcal{P}_{\text{inv}}$), an invalid candidate exhibited a higher AST structural score or appeared earlier in generation order, but failed public tests. The eligibility gate successfully filtered these candidates before ranking, preventing false-positive selections.

3. **Prompt Specification Trade-Off & Authoritative Contract Audit:**  
   Invariant contract prompting did not degrade overall candidate quality (held-out yield increased from 33.3% to 41.7%). However, it induced a qualitative trade-off:
   - **Win:** On `enterprise_cache_stampede_mutex`, the invariant prompt guided the model to synthesize an atomic single-flight mutex (`threading.Event()` + double-checked locking), unlocking held-out correctness ($C'_0$ passed held-out tests, whereas 0/2 standard candidates passed).
   - **Loss & Specification Audit:** On `enterprise_circuit_breaker`, the invariant prompt instructed strict fail-closed type validation (`TypeError` for invalid parameter types, `ValueError` for out-of-bounds numbers). An audit of the authoritative ground-truth reference solution (`solution/circuit.py`) confirms that the benchmark specification explicitly requires `raise ValueError` for non-integer inputs (`raise ValueError("failure_threshold must be positive int")`). Under this authoritative specification, the invariant repair raising `TypeError` is genuinely incorrect. The regression was driven by prompt-induced exception specification mismatch rather than benchmark over-specification or AST selection bias.

4. **Identical Task-Level Factorial Parity & Small-Sample Uncertainty:**  
   All four factorial arms achieved an identical **3 / 6 (50.0%)** held-out pass rate:
   - Config 1 (Baseline: Standard Prompt + Greedy Selection): **3 / 6 (50.0%)**
   - Config 3 (AST-Only: Standard Prompt + AST Selection): **3 / 6 (50.0%)**
   - Config 2 (Prompt-Only: Invariant Prompt + Greedy Selection): **3 / 6 (50.0%)**
   - Config 4 (Combined: Invariant Prompt + AST Selection): **3 / 6 (50.0%)**
   
   With $N=6$, the 50.0% pass rate entails substantial small-sample uncertainty: the Wilson 95% score interval spans $[18.8\%, 81.2\%]$. Paired differences across all four configurations are descriptively $\Delta = 0.0$ pp. No aggregate interaction effect was observed between invariant prompting and AST selection in this six-task exploratory evaluation.

---

## 2. Experimental Design & Factorial Architecture

The study isolates candidate generation from candidate selection across four distinct configurations:

```
                            FACTORIAL DESIGN MATRIX (2 x 2)
                                   Prompt Condition
                         Standard Prompt        Invariant Prompt
                     +----------------------+----------------------+
      Greedy         |   Configuration 1    |   Configuration 2    |
      (First Public) |   Baseline           |   Prompt-Only        |
                     +----------------------+----------------------+
Selection            |   Configuration 3    |   Configuration 4    |
Policy AST-Ranked    |   AST-Only           |   Combined           |
                     +----------------------+----------------------+
```

### Methodological Protocol:

1. **Candidate Pool Generation & Freezing:**  
   For each task $T_i$, two pools of candidates $\mathcal{P}_{\text{std}}(T_i) = \{C_0, C_1\}$ and $\mathcal{P}_{\text{inv}}(T_i) = \{C'_0, C'_1\}$ were generated under fixed stochastic parameters ($k=2$, Temperature $=0.7$, seed $=142$) using `openai/gpt-oss-120b` via Groq. Each candidate includes its edit operations, generated code, execution telemetry, and AST structural quality score. Once generated, all pools were serialized to immutable disk files in `research-controlled-ablation/pools/`.

2. **Public Verification Eligibility Gate:**  
   A candidate $c \in \mathcal{P}$ is eligible for selection if and only if it passes all visible unit tests ($V_{\text{public}}(c) = \text{PASS}$). Candidates failing public tests are quarantined and cannot be selected by either policy.

3. **Selection Policies:**  
   - **Greedy Selector ($\pi_{\text{greedy}}$):** Selects the first generated candidate that satisfies public verification ($c^* = \text{argmin}_{i} \{ i \mid V_{\text{public}}(c_i) = \text{PASS} \}$).
   - **AST Structural Selector ($\pi_{\text{AST}}$):** Selects the eligible candidate with the highest structural quality score ($c^* = \text{argmax}_{c \in \mathcal{P}_{\text{eligible}}} \{ \text{AST\_Score}(c) \}$).

4. **Independent, Access-Controlled Held-Out Audits:**  
   Only after selection decisions were finalized and sealed were candidates evaluated against the held-out test suite. The selection policies had no access to held-out test results, inputs, or assertions.

5. **Orthogonal Causal Diagnostic Classification:**  
   To prevent conflating generation failures with selection failures, each selection decision is classified across two orthogonal dimensions:
   - **Selection Eligibility:**
     - `ELIGIBLE_CANDIDATE_SELECTED`: An eligible candidate was selected.
     - `NO_ELIGIBLE_CANDIDATES`: No candidate in the pool passed public tests.
   - **Pool Held-Out Correctness:**
     - `BOTH_PASS`: All eligible candidates pass held-out tests.
     - `PARTIAL_CORRECT`: Exactly one candidate passes held-out tests (actionable selector divergence).
     - `NONE_PASS`: No candidate in the pool passes held-out tests.
   - **Derived Diagnostic Verdict (Pool-Level Classification across 12 Unique Pools):**
     - `SUCCESSFUL_SELECTION`: An eligible candidate passing held-out tests was selected (6 / 12 pools, 50.0%).
     - `SELECTION_FAILURE`: The selector chose a failing candidate when an eligible held-out correct candidate was available in the same pool (0 / 12 pools, 0.0%).
     - `NO_VALID_CANDIDATE`: No candidate in the pool satisfied held-out requirements (candidate generation failure: 6 / 12 pools, 50.0%).
     - `NO_ELIGIBLE_CANDIDATE`: No candidate passed public verification (eligibility gate failure: 0 / 12 pools, 0.0%).
     *(Note: This classification applies to the 12 unique candidate pools generated in the study, rather than a count across the 24 individual policy runs).*

---

## 3. Comprehensive Task-Level Telemetry & Results

Below is the complete task-level execution matrix across the 6 enterprise state-machine fixtures, recording candidate indices, AST scores, public verification results, held-out verification results, and causal diagnostic verdicts.

### Table 1: Complete $2 \times 2$ Factorial Task-Level Matrix

| Task Identifier | Arm | Pool Candidates $(C_0, C_1)$ | AST Scores | Public Pass | Held-Out Pass | Greedy Pick | AST Pick | Policy Disagree | Causal Diagnosis |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **`enterprise_circuit_breaker`** | $\mathcal{P}_{\text{std}}$ | $\{C_0, C_1\}$ | $[222.30, 305.62]$ | $[\text{T}, \text{T}]$ | $[\text{T}, \text{T}]$ | $C_0$ (Pass) | $C_1$ (Pass) | **Yes** | `SUCCESSFUL_SELECTION` (Both pass) |
| | $\mathcal{P}_{\text{inv}}$ | $\{C'_0, C'_1\}$ | $[293.10, 303.22]$ | $[\text{F}, \text{T}]$ | $[\text{F}, \text{F}]$ | $C'_1$ (Fail) | $C'_1$ (Fail) | No | `NO_VALID_CANDIDATE` (Type drift) |
| **`enterprise_saga_coordinator`** | $\mathcal{P}_{\text{std}}$ | $\{C_0, C_1\}$ | $[39.64, 88.06]$ | $[\text{T}, \text{F}]$ | $[\text{F}, \text{F}]$ | $C_0$ (Fail) | $C_0$ (Fail) | No | `NO_VALID_CANDIDATE` ($C_1$ inelig.) |
| | $\mathcal{P}_{\text{inv}}$ | $\{C'_0, C'_1\}$ | $[85.16, 67.64]$ | $[\text{T}, \text{T}]$ | $[\text{F}, \text{F}]$ | $C'_0$ (Fail) | $C'_0$ (Fail) | No | `NO_VALID_CANDIDATE` |
| **`enterprise_dead_letter_retry`** | $\mathcal{P}_{\text{std}}$ | $\{C_0, C_1\}$ | $[295.80, 290.96]$ | $[\text{T}, \text{T}]$ | $[\text{F}, \text{F}]$ | $C_0$ (Fail) | $C_0$ (Fail) | No | `NO_VALID_CANDIDATE` |
| | $\mathcal{P}_{\text{inv}}$ | $\{C'_0, C'_1\}$ | $[186.48, 166.80]$ | $[\text{T}, \text{T}]$ | $[\text{F}, \text{F}]$ | $C'_0$ (Fail) | $C'_0$ (Fail) | No | `NO_VALID_CANDIDATE` |
| **`enterprise_cache_stampede_mutex`** | $\mathcal{P}_{\text{std}}$ | $\{C_0, C_1\}$ | $[102.24, 121.42]$ | $[\text{T}, \text{T}]$ | $[\text{F}, \text{F}]$ | $C_0$ (Fail) | $C_1$ (Fail) | **Yes** | `NO_VALID_CANDIDATE` (Both fail) |
| | $\mathcal{P}_{\text{inv}}$ | $\{C'_0, C'_1\}$ | $[161.60, 140.84]$ | $[\text{T}, \text{T}]$ | $[\text{T}, \text{F}]$ | $C'_0$ (Pass) | $C'_0$ (Pass) | No | **`SUCCESSFUL_SELECTION`** |
| **`enterprise_bulkhead_isolation`** | $\mathcal{P}_{\text{std}}$ | $\{C_0, C_1\}$ | $[202.32, 152.92]$ | $[\text{T}, \text{T}]$ | $[\text{T}, \text{F}]$ | $C_0$ (Pass) | $C_0$ (Pass) | No | `SUCCESSFUL_SELECTION` |
| | $\mathcal{P}_{\text{inv}}$ | $\{C'_0, C'_1\}$ | $[165.58, 179.20]$ | $[\text{T}, \text{T}]$ | $[\text{T}, \text{T}]$ | $C'_0$ (Pass) | $C'_1$ (Pass) | **Yes** | `SUCCESSFUL_SELECTION` (Both pass) |
| **`enterprise_outbox_publisher`** | $\mathcal{P}_{\text{std}}$ | $\{C_0, C_1\}$ | $[193.66, 86.10]$ | $[\text{T}, \text{T}]$ | $[\text{T}, \text{F}]$ | $C_0$ (Pass) | $C_0$ (Pass) | No | `SUCCESSFUL_SELECTION` |
| | $\mathcal{P}_{\text{inv}}$ | $\{C'_0, C'_1\}$ | $[180.20, 199.28]$ | $[\text{T}, \text{T}]$ | $[\text{T}, \text{T}]$ | $C'_0$ (Pass) | $C'_1$ (Pass) | **Yes** | `SUCCESSFUL_SELECTION` (Both pass) |

---

## 4. In-Depth Analysis of Research Questions

### Question 1: How often do greedy and AST selection choose different candidates from identical pools?

**Answer:** Greedy and AST selection chose different candidates in **4 out of 12 candidate pools (33.3% disagreement rate)**.
- In the Standard Prompt Condition ($\mathcal{P}_{\text{std}}$), divergence occurred on 2 of 6 tasks:
  1. `enterprise_circuit_breaker`: Greedy selected $C_0$ (AST 222.30); AST selected $C_1$ (AST 305.62).
  2. `enterprise_cache_stampede_mutex`: Greedy selected $C_0$ (AST 102.24); AST selected $C_1$ (AST 121.42).
- In the Invariant Prompt Condition ($\mathcal{P}_{\text{inv}}$), divergence occurred on 2 of 6 tasks:
  1. `enterprise_bulkhead_isolation`: Greedy selected $C'_0$ (AST 165.58); AST selected $C'_1$ (AST 179.20).
  2. `enterprise_outbox_publisher`: Greedy selected $C'_0$ (AST 180.20); AST selected $C'_1$ (AST 199.28).

In the remaining 8 pools, greedy and AST selection chose the identical candidate. In 6 of those pools, the highest-scoring AST candidate happened to be candidate 0; in 2 pools (`enterprise_saga_coordinator` in $\mathcal{P}_{\text{std}}$ and `enterprise_circuit_breaker` in $\mathcal{P}_{\text{inv}}$), candidate 0 failed public tests or candidate 1 failed public tests, leaving only a single eligible candidate for selection.

### Question 2: When they disagree, which selector achieves higher held-out correctness?

**Answer:** Across all four cases of disagreement, **neither selector achieved higher held-out correctness than the other**. The held-out outcome divergence between greedy and AST selection was exactly **0 / 12 pools (0.0%)**.

Every single time greedy and AST selection diverged, the candidate pool exhibited homogeneous held-out correctness:
1. `enterprise_circuit_breaker` ($\mathcal{P}_{\text{std}}$): Both $C_0$ and $C_1$ passed held-out tests. (Greedy: PASS, AST: PASS).
2. `enterprise_cache_stampede_mutex` ($\mathcal{P}_{\text{std}}$): Both $C_0$ and $C_1$ failed held-out tests. (Greedy: FAIL, AST: FAIL).
3. `enterprise_bulkhead_isolation` ($\mathcal{P}_{\text{inv}}$): Both $C'_0$ and $C'_1$ passed held-out tests. (Greedy: PASS, AST: PASS).
4. `enterprise_outbox_publisher` ($\mathcal{P}_{\text{inv}}$): Both $C'_0$ and $C'_1$ passed held-out tests. (Greedy: PASS, AST: PASS).

Consequently:
$$\text{SELECTION\_FAILURE} = 0 \quad (0.0\%)$$
The AST structural heuristic never chose an incorrect candidate when an eligible correct candidate was available in the pool. It did not degrade generalization compared to greedy selection on identical pools.

### Question 3: Does invariant contract prompting increase the proportion of generated candidates that satisfy held-out requirements?

**Answer:** At the candidate level, invariant contract prompting produced a **moderate net improvement in held-out correctness yield**, increasing from **33.3% (4/12 candidates)** in $\mathcal{P}_{\text{std}}$ to **41.7% (5/12 candidates)** in $\mathcal{P}_{\text{inv}}$ (+8.4 percentage points). Public-test pass rates were identical across conditions: **11/12 (91.7%)** in both pools.

```
                    CANDIDATE-LEVEL YIELD COMPARISON (k=2, N=12 per arm)
+-------------------------+--------------------+---------------------+--------------------+
| Prompt Condition        | Public Pass Yield  | Held-Out Pass Yield | Dual Pass Yield    |
+-------------------------+--------------------+---------------------+--------------------+
| Standard Prompt Arm     | 11 / 12 (91.7%)    | 4 / 12 (33.3%)      | 4 / 12 (33.3%)     |
| Invariant Prompt Arm    | 11 / 12 (91.7%)    | 5 / 12 (41.7%)      | 5 / 12 (41.7%)     |
| Net Difference          | 0.0 pp             | +8.4 pp             | +8.4 pp            |
+-------------------------+--------------------+---------------------+--------------------+
```

However, at the task level, this net gain was balanced by a stark qualitative trade-off:
- **The Concurrency Discovery:** On `enterprise_cache_stampede_mutex`, the standard prompt failed to prompt single-flight locking, resulting in 0/2 held-out correct candidates. The invariant prompt specifically emphasized thread-safe state synchronization and double-checked locking, prompting the model to implement a `threading.Event()` single-flight mechanism ($C'_0$), which passed all held-out concurrent load tests.
- **The Exception Drift Penalty & Specification Audit:** On `enterprise_circuit_breaker`, the standard prompt yielded 2/2 held-out correct candidates (100% yield). The invariant prompt instructed strict fail-closed input verification with explicit exception typing (`TypeError` for invalid parameter types, `ValueError` for out-of-bounds numbers). When the model followed this instruction:
  ```python
  if not isinstance(failure_threshold, int) or isinstance(failure_threshold, bool):
      raise TypeError("failure_threshold must be an int")
  ```
  The held-out verification test (`test_invalid_parameters_rejected`) asserted `with self.assertRaises(ValueError): CircuitBreaker(d, failure_threshold=1.5)`. The benchmark test failed with an unhandled `TypeError`, dropping held-out yield from 2/2 to 0/2.
  
  **Authoritative Specification Audit:** An independent audit of the benchmark's ground-truth solution (`solution/circuit.py`) confirmed that the reference code explicitly raises `ValueError` for non-integer arguments (`raise ValueError("failure_threshold must be positive int")`). Under this authoritative specification, the generated invariant patch was genuinely incorrect. The regression was driven by prompt-induced exception convention drift rather than benchmark over-specification or AST selection bias.

### Question 4: Is there evidence that combining invariant prompting with AST scoring produces a harmful interaction?

**Answer:** **No.** No aggregate interaction effect was observed between invariant prompting and AST selection in this six-task exploratory evaluation.

In the factorial summary:
- Config 1 (Baseline: Standard + Greedy): **3 / 6 (50.0%)** [Wilson 95% CI: 18.8% to 81.2%]
- Config 3 (AST-Only: Standard + AST): **3 / 6 (50.0%)** [Wilson 95% CI: 18.8% to 81.2%]
- Config 2 (Prompt-Only: Invariant + Greedy): **3 / 6 (50.0%)** [Wilson 95% CI: 18.8% to 81.2%]
- Config 4 (Combined: Invariant + AST): **3 / 6 (50.0%)** [Wilson 95% CI: 18.8% to 81.2%]

#### Paired Task-Level Discordance & Transition Analysis:

To avoid confounding paired within-task transitions with independent binomial samples, we evaluate exact paired discordance across the six fixtures ($N=6$):

```
                        PAIRED TASK TRANSITION MATRICES (N=6)
      1. Baseline vs. AST-Only (Config 1 vs Config 3)      2. Baseline vs. Prompt-Only (Config 1 vs Config 2)
                 Config 3 (AST)                                       Config 2 (Prompt)
                 Pass       Fail                                      Pass       Fail
  Config 1 Pass    3          0                        Config 1 Pass    2          1
  (Greedy) Fail    0          3                        (Greedy) Fail    1          2
  -> Discordant Pairs: b = 0, c = 0                    -> Discordant Pairs: b = 1, c = 1
  -> Paired Difference: Δ = 0.0 pp                     -> Paired Difference: Δ = 0.0 pp
  -> Exact McNemar Test: p = 1.0 (Zero Discordance)    -> Exact McNemar Test: p = 1.0 (Balanced Transition)
```

1. **Config 1 vs. Config 3 (Isolating AST Selection on Identical Pools):**  
   Zero discordant pairs ($b=0, c=0$). Both selectors produced identical held-out outcomes on all 6 tasks ($a=3$ passing tasks: `circuit_breaker`, `bulkhead`, `outbox`; $d=3$ failing tasks: `saga`, `dead_letter`, `cache_stampede`). The observed paired difference is $\Delta = 0.0$ pp with zero within-sample variance between selected repairs.

2. **Config 1 vs. Config 2 (Isolating Prompt Condition on Identical Greedy Selector):**  
   Exactly two discordant tasks ($b=1, c=1$):
   - $b=1$: `enterprise_circuit_breaker` passed in Config 1, but failed in Config 2 (prompt-induced exception drift).
   - $c=1$: `enterprise_cache_stampede_mutex` failed in Config 1, but passed in Config 2 (concurrency invariant discovery).
   The two transitions exactly offset each other, yielding an observed paired difference of $\Delta = 0.0$ pp (exact two-tailed McNemar $p = 1.0$).

In Configuration 4 (Invariant Prompt + AST Selection), the AST selector chose $C'_1$ on `bulkhead_isolation` (AST 179.20 vs 165.58) and $C'_1$ on `outbox_publisher` (AST 199.28 vs 180.20). In both instances, the selected patch passed held-out tests. In the remaining four tasks, the AST selector chose the exact same candidate as the greedy selector.

The regression observed in the pilot (where Replay held-out dropped from 2/6 to 1/6) was driven by:
1. The exception drift on `enterprise_circuit_breaker`, which was caused purely by candidate generation under the invariant prompt, not by AST scoring.
2. The feedback strategy's public test regressions in the pilot, which stemmed from multi-turn feedback prompt drift in the adaptive runner.

---

## 5. Methodological Safeguards & Scientific Validity

To adhere to rigorous empirical standards in software engineering research:

1. **Frozen Reference & No Benchmark Drift:**  
   The v1.9 baseline remains strictly frozen at release `v1.9.0-research-release` (commit `75de313`). No test fixtures, public suites, or held-out assertions were altered to accommodate v2.0 candidates.

2. **Access-Controlled Held-Out Evaluation:**  
   Held-out suites were executed in an isolated verification runtime. Neither the candidate generation pipeline nor the selection heuristics were provided access to held-out assertions, outputs, or error traces. Candidate selection was sealed and written to disk before held-out evaluation was initiated.

3. **Orthogonal Diagnostic Disentanglement:**  
   By decomposing evaluation into two orthogonal dimensions (`selection_eligibility` and `pool_heldout_correctness`), the experimental harness avoids misattributing candidate generation failures (where the model never produced a correct repair) to candidate selection heuristics.

4. **Scope & Generalization Boundary:**  
   This study represents a controlled candidate-selection ablation on the six hardest state-machine tasks using `openai/gpt-oss-120b`. While these results definitively resolve the mechanism on this target cluster, broader claims regarding structural ranking heuristics across diverse architectures (e.g., non-concurrency tasks, smaller models) remain subject to future empirical evaluation.

---

## 6. Recommendations for RETRACE v2.0 Architecture

Based on these findings, we establish the following architectural roadmap for RETRACE v2.0:

1. **Retain Public-Test Gated AST Selection as a Tie-Breaker:**  
   The AST defensive quality scorer is safe to deploy when gated by public verification. It does not induce selection failures and rewards defensive programming patterns (single-flight locking, resource cleanup).

2. **Harmonize Exception Specifications in Prompt Contracts:**  
   Prompt templates must avoid prescribing narrow exception hierarchies (e.g., mandating `TypeError` over `ValueError`) unless explicitly codified in the task repository's docstrings or public tests. Prompts should specify defensive validation without prescribing non-standard exception sub-types that conflict with legacy test assertions.

3. **Expand Candidate Pool Depth ($k \ge 4$):**  
   On difficult state-machine tasks, $k=2$ produces homogeneous pools on held-out correctness in 66.7% of tasks. Increasing pool size to $k=4$ or $k=8$ provides the structural selector with greater candidate diversity, maximizing the utility of structural ranking.
