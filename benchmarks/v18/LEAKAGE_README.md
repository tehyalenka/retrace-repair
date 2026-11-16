# Leakage-resistant paired evaluation (experimental)

This extension separates **public repair feedback** from **heldout final verification**.
The public verifier is run during agent attempts and can appear in repair prompts.
The heldout verifier runs **once after each arm finishes**, in a separate copy of the original repository with final edits applied. Heldout failures do not trigger another repair.

For the included offline plumbing fixture:

```bash
PYTHONPATH=src:. python -m benchmarks.v18.leakage_resistant capture \
  --mode offline --case bugfix --output public-capture.json \
  --public-verifier benchmarks/v18/verifiers/double_public.py \
  --heldout-verifier benchmarks/v18/verifiers/double_heldout.py

PYTHONPATH=src:. python -m benchmarks.v18.leakage_resistant evaluate \
  --trace public-capture.json --output leakage-offline.json --offline \
  --public-verifier benchmarks/v18/verifiers/double_public.py \
  --heldout-verifier benchmarks/v18/verifiers/double_heldout.py

PYTHONPATH=src:. python -m benchmarks.v18.summarize_leakage --input leakage-offline.json
```

For **live** trials, create distinct public and heldout unittest files for each task and capture a *new* initial failed attempt using `--mode live --case bugfix|feature|refactor` (without `--offline`), then evaluate that trace without `--offline`. A capture must fail **public** verification. The original `paired-capture.json` is NOT compatible because it was captured using the original verifier. Existing v11 hidden tests must be partitioned/curated, not reused as public feedback.

The report checkpoint binds the public trace and heldout verifier SHA-256; changing either requires a new output file. Keep private heldout files out of the agent repository and never place them in prompts or model context. Test execution is **not a security sandbox**; run only trusted code.

## Limitations

- This is a mechanism/measurement extension, not a 10–15 task benchmark dataset.
- Offline repairs are scripted, not autonomous.
- Heldout tests are run only after repair, but their results are stored in the local report; review reports before publication.
- `run_verification` executes smoke tests as well as the injected heldout test; `tests_run` includes both.
- An independent heldout test suite is only as strong as its coverage; passing is not proof of general correctness.
- Live API calls may be billable. The existing checkpoint stores prompts, code, and model responses.
