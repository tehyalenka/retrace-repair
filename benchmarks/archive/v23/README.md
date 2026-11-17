# v2.3 Challenging Repository Benchmark

Three new Python repository tasks: checkout idempotency/atomicity, document access control, and event log consistency. They use independent verification and the v2.2 natural-first-attempt paired replay. No initial defects are seeded.

Run live: `PYTHONPATH=src:. python3 -m benchmarks.v23.challenging_recovery --mode live --repeats 1 --cooldown 90 --output v23-live.json`

Resume: add `--resume` to the identical command. Offline mode tests harness plumbing only and does not measure LLM ability. Results from three hand-designed tasks are not representative of real-world repositories. Review traces before publishing.
