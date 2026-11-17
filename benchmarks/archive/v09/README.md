# CodePilot-X v0.9 independent-test benchmark

Three deliberately small but cross-module Python challenges: bugfix, feature, and refactor.
The agent sees the task description, repository map, and retrieved source, **not the independent test source**. Its existing verification mechanism does expose failure output on repair attempts; therefore this is *not a fully blind benchmark*.

Run from the project root (with the venv activated and `GROQ_API_KEY` configured):

```bash
python3 benchmarks/v09/evaluate.py --case bugfix --attempts 3
python3 benchmarks/v09/evaluate.py --case all --attempts 3 --output benchmark-v09-result.json
```

Optional `--generate-tests` also uses Groq to generate tests, increasing API usage.
Do not edit benchmark cases or hidden tests while comparing runs. Each case is copied into a temporary directory, and the originals are not modified. The evaluator reports per-case success, first-attempt pass, attempts used, elapsed time, and test feedback. Independent tests are intentionally stronger than the included smoke tests, but passing them does not prove general real-world capability.

**Safety:** The agent executes repository code and independent tests locally, without an OS sandbox. Run only trusted fixtures.
