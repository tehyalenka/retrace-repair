# Enterprise order contract v2

This incremental patch changes only the **public** verifier for `enterprise_order_atomicity`. It does not overwrite the hardened runner, the held-out verifier, or existing experiment reports.

The public verifier now covers two explicitly documented business rules: zero quantity must raise `ValueError` without side effects, and a reused idempotency key with a conflicting quantity must raise `ValueError` without side effects. Held-out verification retains additional invalid quantity variants and other transactional invariants.

Apply the revised task description from the prior conversation before running this patch's experiment. Preserve old reports and use a new output directory. This is a new benchmark version, so do not directly pool results with v1.
