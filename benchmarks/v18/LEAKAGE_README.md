# Leakage-Resistant Dual-Suite Protocol & Formal Isolation Proof

RETRACE enforces strict cryptographic and filesystem boundaries between **public smoke tests** (accessible during repair) and **held-out contract tests** (evaluated strictly post-repair).

## Formal Isolation Architecture

```
+-----------------------------------------------------------------------------------+
| Host Benchmark Harness (benchmarks/v18/task_suite/)                               |
|   ├── <task_id>/repo/                 Defective seed implementation               |
|   ├── <task_id>/solution/             Reference solution (NEVER copied to agent)  |
|   ├── <task_id>/public.py             Smoke test verifier                         |
|   └── <task_id>/heldout.py            Contract verifier (NEVER copied to agent)   |
+-----------------------------------------------------------------------------------+
                                         │
                        fixture()        │ Isolated Temporary Directory
                        Creation         │ (/tmp/retrace-task-XXXXX/)
                                         ▼
+-----------------------------------------------------------------------------------+
| Disposable Agent Workspace                                                        |
|   ├── <source_files>.py               Defective seed code                         |
|   └── tests/test_public.py            public.py ONLY                              |
|                                                                                   |
|  [FORBIDDEN & PHYSICALLY ABSENT]:                                                 |
|    ✗ heldout.py                                                                   |
|    ✗ solution/                                                                    |
|    ✗ manifest.json                                                                |
+-----------------------------------------------------------------------------------+
                                         │
               Agent Repair Loop         │ Context Retrieval: discover_python_files()
               (Resample / Feedback /    │   - Scoped strictly to Disposable Workspace
                Counterfactual Replay)   │   - Excludes tests/ and __pycache__/
                                         ▼
+-----------------------------------------------------------------------------------+
| Candidate Generation & Public Test Selection                                      |
|   - Replay arm evaluates candidate branches in disposable sub-workspaces          |
|   - Candidate selection strictly uses public test pass/fail metrics               |
|   - Held-out contract verifiers are NOT accessible during candidate selection     |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼ Final Patch Selected
+-----------------------------------------------------------------------------------+
| Post-Repair Independent Held-Out Verification                                     |
|   - Executes in an isolated process with PYTHONPATH pointing to patched repo      |
|   - Runs strictly ONCE after repair terminates                                    |
|   - Test failure outputs NEVER feed back into agent prompt or repair loop         |
+-----------------------------------------------------------------------------------+
```

## Formal Isolation Guarantees

1. **Filesystem Boundary**:
   The `task_suite_runner.fixture()` function copies exclusively the task repository source files into a fresh temporary workspace. The held-out test file (`heldout.py`) and reference solution (`solution/`) are never copied, symlinked, or made readable within the agent's working directory.

2. **Context Retrieval Scoping**:
   The agent's repository scanner (`discover_python_files()`) traverses only the disposable workspace directory and explicitly ignores `tests/` and `__pycache__/`. It is mathematically impossible for the agent to retrieve held-out verifier code into prompt contexts.

3. **Candidate Selection Without Leakage**:
   In `counterfactual_replay`, candidate patches generated across speculative branches are evaluated solely against `tests/test_public.py`. The candidate selection policy chooses the best candidate using public test pass status, edit distance, and syntax validity without any interaction with held-out verifiers.

4. **Post-Repair Execution Only**:
   The held-out verification step executes strictly after the autonomous repair policy completes. If a candidate passes public tests but fails held-out tests, the failure trace is recorded in benchmark output JSON but is never fed into another repair attempt.

5. **Continuous Verification**:
   The regression test `test_fixture_isolation_no_heldout_or_solution_leakage` in `tests/test_v18_task_suite.py` executes across all 45 benchmark tasks, asserting that:
   - No file matching `*heldout*` or `*solution*` exists in any agent workspace.
   - No string from `heldout.py` appears in any source file in the agent workspace.
   - Public test fixtures exist solely under `tests/test_public.py`.
