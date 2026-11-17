# RETRACE: multi-file adversarial verifier audit

This offline benchmark checks verifier sensitivity, not autonomous repair success.

Three cooperating Python modules implement stock reservation, payment, and order idempotency. The reference implementation must pass a basic public test and four independent held-out tests. Three deliberately faulty variants each preserve the public happy-path behavior but break a distinct invariant:

1. Payment failure must restore stock.
2. Duplicate order IDs must not decrement stock twice.
3. Multi-item reservations must be atomic when later items are insufficient.

The held-out suite also rejects invalid quantities. Every mutant is expected to pass the public suite and fail the held-out suite. This is a controlled demonstration of public-test overfitting risk; it is not evidence that RETRACE can repair these defects.

Run: `PYTHONPATH=src:. python3 -m unittest tests.test_multifile_adversarial -v`

Optional report: `PYTHONPATH=src:. python3 -m benchmarks.v18.multifile_adversarial`

Limitations: synthetic 3-module repository, no concurrency, no external real-world defects, no model requests, and no secure sandbox. Only run trusted fixtures.
