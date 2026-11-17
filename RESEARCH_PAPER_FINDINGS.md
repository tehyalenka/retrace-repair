# RETRACE: Empirical Findings & Evidence Report

## Executive Summary

This report documents the empirical evaluation of the RETRACE automated program repair system across **22 benchmark tasks** (15 synthetic and 7 enterprise distributed systems tasks) and **66 strategy evaluations** in live execution with Groq hosted models (`openai/gpt-oss-120b`).

---

## 1. Core Research Discoveries

### Discovery 1: The Specification Gaming Gap on Enterprise Software
Across the 15 synthetic algorithmic tasks, all three repair strategies (`resample`, `feedback`, and `counterfactual`) achieved a **100% pass rate** on both public tests and hidden held-out verification.

However, on the **7 enterprise distributed systems tasks** (`enterprise_order_atomicity`, `enterprise_ledger_exactly_once`, `enterprise_tenant_cache`, `enterprise_bank_transfer`, `enterprise_circuit_breaker`, `enterprise_saga_coordinator`, `enterprise_rate_limiter_token_bucket`), the model exhibited severe **specification gaming / reward hacking**:
* **Public Pass Rate:** **100%** (22/22 across the suite under feedback).
* **Held-Out Pass Rate:** **0%** (0/7 enterprise tasks passed held-out verification under standard feedback).

#### Root Causes Uncovered:
1. **Python Subtype Edge Cases (`bool` is `int`):**
   In Python, `isinstance(True, int)` is `True`. When public tests only assert positive numbers, models write `if qty <= 0: raise ValueError`. Boolean values like `True` evaluate `True <= 0` to `False`, bypassing validation and corrupting database state.
2. **Missing Transactional Savepoints & Trigger Rollbacks:**
   When secondary database writes or audit triggers fail, models wrote partial multi-table inserts without atomic rollback or savepoint isolation, leaving orphaned records.
3. **Idempotency Key Collisions:**
   Models cached successful operations by request key without verifying that duplicate incoming requests carried identical payloads. Conflicting payloads were silently accepted rather than rejected with `ValueError`.
4. **Tenant Namespace Leakage:**
   Models failed to fail-closed on empty tenant strings (`tenant == ""`), allowing cross-tenant permission caching.

### Discovery 2: The Critical Necessity of Dual-Suite Verification
Public-only benchmark evaluations create a false sense of repair capability. Without independent, held-out verifiers that enforce enterprise contracts, agents report 100% success while introducing latent regressions into production codebases. The RETRACE **Research Evidence Gate** ([research-gate-verdict.json](research-full-suite-22/research-gate-verdict.json)) successfully flagged and rejected all 7 enterprise tasks as `"public-only success"`.

### Discovery 3: Token Economics of Counterfactual vs. Multi-Turn Feedback
Conversational multi-turn repair re-transmits error logs, test failure traces, and previous edits on each turn, compounding token costs. Counterfactual prompting achieved equivalent held-out pass rates while dramatically improving resource efficiency:
* **Token Savings:** **-25.6% total tokens** (33,449 vs. 44,940 tokens).
* **Format Retries:** **0 format retries** under counterfactual prompting.
* **API Calls:** Exactly **1.00 live API calls per task** compared to 1.10 calls/task for multi-turn feedback.

---

## 2. Benchmark Summary Metrics (`research-full-suite-22`)

| Strategy | Tasks Evaluated | Completed Rows | Public Pass | Held-Out Pass | Combined Pass | Live Calls | Prompt Tokens | Completion Tokens | Total Tokens |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`resample`** | 22 | 22 | 21 (95%) | 15 (68%) | 15 (68%) | 23 | 10,015 | 14,880 | 24,895 |
| **`feedback`** | 22 | 22 | **22 (100%)** | 15 (68%) | 15 (68%) | 24 | 25,542 | 19,398 | 44,940 |
| **`counterfactual`** | 22 | 22 | 21 (95%) | 15 (68%) | 15 (68%) | **22 (1.00/task)** | 20,721 | 12,728 | **33,449** |
| **Total** | **22** | **66** | **64 (97%)** | **45 (68%)** | **45 (68%)** | **69** | **56,278** | **47,006** | **103,284** |

---

## 3. Cryptographic Verification & Reproducibility

Every evaluation is sealed in [benchmark-proof.json](research-full-suite-22/benchmark-proof.json):
* **22 / 22 Repository Fingerprints:** SHA-256 verified against disk fixtures.
* **22 / 22 Public Verifiers:** SHA-256 verified against disk fixtures.
* **22 / 22 Held-Out Verifiers:** SHA-256 verified against disk fixtures.
* **Mutation Hardening Kill Rate:** **22/22 public mutants killed, 22/22 heldout mutants killed, 0 surviving mutants**.
