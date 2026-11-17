# RETRACE EnterpriseBench — initial executable pack

Three **synthetic enterprise-inspired** Python/SQLite tasks are added to the existing 15-fixture suite (18 total):

- `enterprise_order_atomicity`: order retries, atomic stock decrement, transactional outbox, fault rollback.
- `enterprise_ledger_exactly_once`: duplicate financial events, conflicting replay, atomic balance updates.
- `enterprise_tenant_cache`: cross-tenant cache isolation and permission revocation freshness.

These are local simulations, **not** independently sourced production defects or actual distributed systems. SQLite transactions are deterministic; no claim of network partition, real distributed concurrency, or production realism is made.

## Install

From `~/Desktop/retrace-repair`, unzip the downloaded patch ZIP using `unzip -o ~/Downloads/RETRACE_EnterpriseBench_v1.zip`.

## Validate offline

`PYTHONPATH=src:. python3 -m benchmarks.v18.task_suite_runner validate`

Expected: 18 fixtures with initial public failure, passing reference public and held-out checks.

`PYTHONPATH=src:. python3 -m unittest discover -s tests -p 'test_*.py'`

## Controlled live comparison

`PYTHONPATH=src:. python3 -m benchmarks.v18.task_suite_runner live --task enterprise_order_atomicity --output-dir research-enterprise-v1 --repetitions 1 --attempts 3 --max-http-requests-per-arm 2`

**Caution:** task_suite_runner injects the initial failed completion, so these are controlled-failure continuations, not natural first-attempt failures. Report results as such. Generated traces can include prompts and code; do not commit without review. The verifier runner executes arbitrary code and is not a security sandbox.

## Limits and next steps

The three tasks are more stateful than original arithmetic fixtures, but are still small synthetic benchmarks. Expand with independent real-world bug reproductions, deterministic concurrency schedules, mutation testing, and stronger non-leakage checks before claiming enterprise-level generalization.
