# RETRACE

**Repository-aware program repair testbed with local test feedback, multi-candidate replay evaluations, and enterprise invariant verification.**

RETRACE is an automated Python program repair evaluation testbed and research benchmark. It retrieves relevant repository context, requests structured multi-file edits from language models, validates syntax and operations, executes tests in isolated disposable workspaces, and evaluates repair policies under controlled, leakage-resistant conditions. **It does not mutate the original repository.**

---

## Capabilities & Key Features

* **Multi-Arm Repair Policies:**
  * `standard`: Bounded multi-turn failure feedback restart.
  * `counterfactual`: Prompt-guided falsifiable alternative hypothesis reasoning.
  * `counterfactual_replay`: Best-of-N candidate patch exploration evaluated against local test suites and ranked deterministically without touching held-out tests.
* **Defensive Enterprise Invariants:**
  * Strict type validation (explicit rejection of `bool` subtypes for integers and numbers).
  * Transactional atomicity and savepoint rollbacks on secondary write failures.
  * Strict idempotency key conflict detection.
  * Fail-closed multi-tenant boundary isolation.
* **Autonomous Benchmark Execution:**
  * Headless daemon with automatic HTTP 429 exponential backoff, sliding-window rate limit handling, and durable checkpoint resumption.
* **Cryptographic Evidence & Mutation Hardening:**
  * Built-in Research Evidence Gate verifying 100% SHA-256 fixture integrity.
  * Multi-operator mutation hardening suite evaluating comparison inversions, return alterations, off-by-one errors, and statement deletions across public and held-out verifiers.

---

## Quickstart

Requires Python 3.9+ and, for live model evaluations, an API key for Groq, OpenAI, or Gemini.

```bash
# 1. Setup virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dashboard,test]"

# 2. Run the full unit regression suite (258 tests)
python3 -m unittest discover -s tests -p 'test_*.py'

# 3. Explore repository mapping and semantic search
retrace map examples/sample_repo
retrace search examples/sample_repo 'fix authentication'
```

### Running the Repair Agent

Configure your preferred LLM provider in `.env` or export in your shell:

```bash
# In .env (recommended, automatically discovered):
GROQ_API_KEY=gsk_...
# Or:
# OPENAI_API_KEY=sk-...
# GEMINI_API_KEY=AIza...

# Execute repair with candidate replay
retrace agent examples/sample_repo \
  "Make username matching case-insensitive while preserving password validation" \
  --repair-policy counterfactual_replay \
  --attempts 2 \
  --output retrace-result.json
```

---

## The v1.8 Benchmark Suite (22 Tasks)

The benchmark evaluates repair policies across **15 synthetic algorithmic tasks** and **7 enterprise distributed systems tasks**:

| Category | Tasks | Tested Invariants |
| :--- | :--- | :--- |
| **Bugfix & Feature** (7) | `clamp_bounds`, `deduplicate`, `average_empty`, `normalize_whitespace`, `slugify`, `running_total`, `group_counts` | Numerical bounds, deduplication, string slugification, accumulator state |
| **Refactoring** (3) | `refactor_sort`, `refactor_default`, `refactor_copy` | Pure refactoring preserving external invariants |
| **Multi-File** (3) | `multifile_discount`, `multifile_tax`, `multifile_inventory` | Coordinated cross-module data model changes |
| **Regression** (2) | `regression_negative`, `regression_case` | Historical regression prevention |
| **Enterprise** (7) | `enterprise_order_atomicity`, `enterprise_ledger_exactly_once`, `enterprise_tenant_cache`, `enterprise_bank_transfer`, `enterprise_circuit_breaker`, `enterprise_saga_coordinator`, `enterprise_rate_limiter_token_bucket` | Concurrency locks, idempotency conflicts, transactional rollback, reverse compensation order, fail-closed tenant isolation, token bucket refill |

### Running Benchmark Validation & Hardening

```bash
# 1. Validate all 22 tasks for self-consistency
python3 -m benchmarks.v18.task_suite_runner validate

# 2. Run mutation hardening (kills mutants in public and heldout verifiers)
python3 -m benchmarks.v18.hardening

# 3. Run autonomous benchmark daemon (handles 429 backoff automatically)
python3 -m benchmarks.v18.autonomous_runner \
  --output-dir research-full-suite-22 \
  --repetitions 1 --attempts 2 --retry-interval-seconds 240
```

---

## Empirical Benchmark Evidence (`research-full-suite-22`)

Evaluated live on Groq (`openai/gpt-oss-120b`) across all 22 tasks and 66 policy evaluations:

| Repair Strategy | Evaluations | Live Calls | Public Pass | Held-Out Pass | Provider-Reported Tokens | Efficiency Delta |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **`resample`** | 22 / 22 | 23 | 21/22 (95%) | 15/22 (68%) | 24,895 | Baseline |
| **`feedback`** | 22 / 22 | 24 | **22/22 (100%)** | 15/22 (68%) | 44,940 | +34.3% tokens |
| **`counterfactual`** | 22 / 22 | **22 (1.00/task)** | 21/22 (95%) | 15/22 (68%) | **33,449** | **-25.6% tokens vs feedback** |
| **Grand Total** | **66 / 66** | **69** | **64/66 (97%)** | **45/66 (68%)** | **103,284** | Cryptographically verified |

> [!NOTE]
> **Token Accounting:** Metrics above represent provider-verified tokens reported in API response payloads (`request_accounting`). The statistical audit (`benchmarks/v18/statistical_analysis.py`) strictly segregates provider-reported tokens from heuristic word estimates, rejecting any silent fallback.

### Key Research Insights

1. **The Public vs. Held-Out Generalization Gap:**
   - **15/15 Synthetic Tasks:** Passed both public and hidden held-out tests across all conditions (ceiling effect).
   - **7/7 Enterprise Tasks:** Models scored **100% on public tests** under feedback repair, but **0% on held-out tests** due to specification gaming (omitting strict parameter types like `bool` checks or secondary table rollback savepoints).
   - **The Research Gate Guardrail:** [research-gate-verdict.json](research-full-suite-22/research-gate-verdict.json) successfully flagged and rejected all 7 enterprise tasks as `"public-only success"`, preventing false claims of repair.

2. **Statistical Significance & Paired Analysis:**
   - Evaluated with exact two-tailed McNemar tests on strictly paired tasks (`paired_evaluable_tasks = 22`, dropped missing tasks = 0).
   - Pairwise $p = 1.0$ across all conditions (`resample` vs `feedback`, `feedback` vs `counterfactual`, `resample` vs `counterfactual`). Because the 15 synthetic tasks passed and 7 enterprise tasks failed across all three arms, the current single-shot evaluation reveals **no statistically significant correctness advantage** for prompt-guided counterfactual reasoning over feedback or resample.
   - **Prompting vs. Replay Delineation:** Prompt-guided `counterfactual` conditioning differs from executable multi-candidate `counterfactual_replay` (best-of-N candidate exploration ranked deterministically by local test execution without held-out leakage), which is currently under active multi-trial evaluation.

---

## Repository Layout

| Directory / File | Purpose |
| :--- | :--- |
| `src/retrace/` | Primary package namespace providing forward-compatibility and public API |
| `src/codepilot/` | Core agent engine, retrieval analyzer, replay candidate strategies, and CLI |
| `benchmarks/v18/` | Active v1.8 benchmark suite runner, autonomous runner, research gate, and task fixtures |
| `benchmarks/archive/` | Historical benchmark iterations (`v09` through `v30`) preserved with version index |
| `backend/` | Optional FastAPI local dashboard API with multi-policy support |
| `frontend/` | Angular local research dashboard |
| `tests/` | 258 unit and regression tests (edit safety, provenance, replay, hardening, statistical analysis) |
| `research-full-suite-22/` | Cryptographic evidence, metrics, SVG coverage charts, and proof JSON |
| `EXPERIMENT_MANIFEST.json` | Complete cryptographic provenance manifest (commit SHA, input hashes, artifact digests) |
| `LICENSE` | Official MIT License |

---

## Security, Edit Safety & Execution Model

RETRACE enforces rigorous boundaries separating patch application safety from execution containment:

1. **Edit Containment & Rollback Safety:**
   - **Path Traversal Rejection:** Patches referencing `../` or nested escape sequences are rejected before modification.
   - **Absolute Path Barring:** Edits targeting absolute filesystem paths (e.g., `/etc`, `/tmp`) raise explicit validation errors.
   - **Symlink Escape Protection:** Symlinks resolving outside the target workspace are blocked from modification.
   - **Extension Filtering:** Non-Python files (`.sh`, `.exe`, dotfiles) are excluded from patch targets.
   - **Repository Allowlisting:** Edits are restricted strictly to files identified during intake or explicitly allowlisted.
   - **Transactional Rollback:** Multi-file modifications use two-phase staging; any disk write or verification failure cleanly rolls back modified and newly created files to their exact pre-edit state.

2. **Runtime Execution & Sandbox Boundary:**
   - **Disposable Workspaces:** Candidate evaluations run inside isolated temporary working directories (`tempfile.TemporaryDirectory`).
   - **No Network Egress During Replay:** Local test runners execute strictly offline test fixtures.
   - *Kernel-Level Sandboxing Distinction:* Current execution containment operates at the filesystem workspace and process boundary. Production environments requiring defense against untrusted arbitrary code execution should wrap test runs in containerized OS sandboxes (e.g. gVisor, Docker, or seccomp).
