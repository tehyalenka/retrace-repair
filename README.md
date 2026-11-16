# RETRACE

**Counterfactual Replay for Repository-Aware Autonomous Program Repair**


A lightweight **repository-aware Python coding agent** that indexes Python source files, retrieves relevant code, requests complete-file edits from a hosted LLM, and tests proposed changes in a temporary repository copy. The original repository is not modified.

**Status:** v0.6.0 local release candidate. Groq end-to-end and v0.6 multi-file benchmark runs require your own API credentials; local unit tests run without network access.

## Features

- Python AST-based function, class, and import inventory
- Lexical task-aware retrieval of repository context
- Groq or OpenAI chat-completions backend via `requests`
- Validated JSON edits restricted to existing Python files
- Whole-batch validation before writing changes
- Temporary workspace with feedback-driven retries
- Existing-test checks, plus optional independently authored task-specific verification tests
- JSON results containing attempt history and final proposed files
- Paired baseline-versus-verification multi-file synthetic benchmark

## Requirements

Python 3.9+; a Groq API key (default) or OpenAI API key for agent execution. On older macOS Python 3.9 environments the dependency constraint keeps `urllib3` below version 2 to avoid LibreSSL compatibility warnings.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e .
python3 -m unittest discover -s tests -v
```

## Configure API

```bash
export CODEPILOT_PROVIDER=groq
export GROQ_API_KEY='YOUR_KEY_HERE'
# Optional: export CODEPILOT_MODEL='openai/gpt-oss-120b'
```

**Never commit API keys or `.env` files.** The default Groq model is `openai/gpt-oss-120b`; availability depends on the provider. To use OpenAI instead, set `CODEPILOT_PROVIDER=openai` and `OPENAI_API_KEY`.

## Usage

```bash
python3 -m codepilot.cli index examples/sample_repo
python3 -m codepilot.cli search examples/sample_repo 'fix authentication'
python3 -m codepilot.cli agent examples/sample_repo \
  'Make username matching case-insensitive while preserving password validation' \
  --attempts 2 --output codepilot-result.json
```

Review the JSON `files` field before manually applying any proposed changes. CodePilot-X does **not** write to your original repository.

## Evaluation

Earlier experimental scripts are retained in `scripts/evaluate_v03.py`, `evaluate_v04.py`, `evaluate_v05.py`, and `evaluate_v051.py`. These are historical prototypes, not a unified benchmark suite.

**Locally observed results (user-run, synthetic tasks):**

| Experiment | Observed outcome | Qualification |
| --- | --- | --- |
| v0.3 | 3/3 hidden-test task success | Small single-file pilot |
| v0.4 corrected | 20/20 hidden-test task success | One run, synthetic single-file tasks; corrected a `numbers` module collision |
| v0.5 | 4/4 completed paired comparisons succeeded | Fifth task aborted due to verifier parsing; no improvement demonstrated |
| v0.5.1 | 5/5 injected faults detected and repaired | Hand-authored checks; no baseline comparison |

**v0.6 paired multi-file study** (results not yet measured):

```bash
python3 scripts/evaluate_v06.py --limit 1 --attempts 2 --repeats 1 --output benchmark-v06-smoke.json
python3 scripts/evaluate_v06.py --limit 3 --attempts 2 --repeats 3 --output benchmark-v06.json
```

Each condition begins with identical source code. The baseline relies on repository tests. The verification condition also runs independently authored task-specific tests and can retry on failure. Both are evaluated using separate hidden tests. The benchmark reports per-task outcomes and paired aggregate success rates; **do not claim improvement unless measured**. Note that baseline success on these synthetic tasks may still be high.

## Architecture

1. `repository_analyzer.py` discovers Python files, parses AST metadata, and retrieves relevant context.
2. `agent.py` asks a hosted model for structured complete-file edits.
3. Proposed edits are checked for allowed paths, duplicate targets, size, and Python syntax before writing.
4. Edits are applied to a disposable copy; discovered `unittest` tests run there.
5. Optional independent task verification provides additional feedback; unsuccessful attempts are retried from a clean copy.
6. The agent returns a JSON report and proposed file contents.

## Limitations and security

- **Not a sandbox.** Generated Python and repository tests run locally with the user's privileges. Use only trusted repositories and review code before running it. Do not use this on confidential or proprietary code without authorization.
- The current agent only edits existing `.py` files and returns complete-file replacements; it cannot create new files.
- Retrieval is lexical rather than embedding-based; large or complex repositories may be truncated by context limits.
- Passing tests is not proof of correctness. The optional verifier uses independently supplied tests; it is not yet an LLM-generated verifier.
- Tests that depend on uninstalled packages or nonstandard discovery may fail. The runner requires at least one discovered unittest case.
- Synthetic benchmarks are not representative of SWE-bench or production engineering performance.
- Runtime depends on API network availability, rate limits, and model behavior. Results may vary between runs.

## Project layout

```text
src/codepilot/          Core agent, repository analyzer, CLI
scripts/                Historical evaluation scripts and v0.6 paired study
tests/                  Offline unit tests
examples/               Minimal sample repository
```

## Reproducibility

Use Python 3.9+, record `CODEPILOT_PROVIDER`, `CODEPILOT_MODEL`, attempt limit, repeat count, and the raw JSON benchmark outputs. API keys must not be included in published results. See `scripts/evaluate_v06.py` for task definitions and hidden checks. For a stronger study, expand to externally sourced multi-file tasks and report uncertainty intervals and token cost.

## License

No license is included yet. Choose and add an appropriate license before public distribution.

## v0.7: Multi-file operation milestone (development build)

Version 0.7 introduces `codepilot map <repository>` for a compact module/symbol/import inventory and extends the agent's JSON edit format with an optional `operation` field (`modify`, `create`, `delete`). Existing edits without `operation` remain modifications. Create operations are limited to new `.py` files under existing directories; modifications/deletions require indexed existing `.py` files. All operations are validated before applying changes, and write errors trigger best-effort rollback. The original repository remains untouched.

Example model output:

```json
{"reasoning_summary":"Introduce a shared policy and update the service", "edits":[{"path":"policy.py","operation":"create","content":"def allowed(role):\n    return role == 'admin'\n"},{"path":"service.py","operation":"modify","content":"from policy import allowed\n"}]}
```

**Validation status:** 14 local unit/integration tests pass, including a mocked-model, three-file feature scenario. This does **not** establish autonomous performance on complex multi-file tasks. The previous v0.6 benchmark remains a small synthetic baseline (9/9 successful runs in each configuration, with only one file modified per run). Live v0.7 model evaluation, real-world repository tasks, safe execution isolation, new-directory creation, non-Python files, and robust dependency analysis remain future work. The temporary copy is **not a security sandbox**; run only on trusted code.

Run locally:

```bash
python3 -m pip install -e .
python3 -m unittest discover -s tests -v
python3 -m codepilot.cli map examples/sample_repo
python3 -m codepilot.cli agent examples/sample_repo "Improve login validation" --output result.json
```

Do not publish this development build as a proven general-purpose autonomous software engineer.

## v0.8 experimental generated verification

Enable independently generated behavioral checks with `--generate-tests`:

```bash
python3 -m codepilot.cli agent examples/sample_repo \
  "Add role-based authorization in a new permissions.py and delegate from auth.py, preserving login behavior" \
  --attempts 3 --generate-tests --output generated-verification-result.json
```

The agent requests a unittest suite **before** implementation, runs it with the repository's tests, and feeds failures into subsequent attempts. The output includes `generated_test_status`, `generated_test_source`, and per-attempt `generated_tests_passed`/`generated_tests_output`. If test generation fails, the run fails closed rather than reporting success. Existing CLI usage and external hand-authored verification remain supported.

**Limitations:** LLM-generated tests can misunderstand requirements, be weak, or be wrong; passing them is not independent proof of correctness. Generated tests execute Python code and are **not sandboxed**. Use trusted repositories only, review generated test source and resulting diffs, and do not provide secrets. Each generated-verification run adds an LLM request and may consume extra API quota. This is an experimental development build, not a production-ready coding agent.

### v0.8.1 test-generation parsing fix

If Groq double-escapes newline characters in generated Python tests, CodePilot-X
now attempts a narrow normalization and validates the result. Invalid generated
suites trigger up to two corrective model requests; if generation still fails,
no implementation edits are applied. These retries consume additional API quota.
This is a parser reliability improvement, not a guarantee of correct generated tests.


## v1.5 controlled retrieval evaluation

Run `python3 benchmarks/v15/evaluate.py --max-files 2 --output benchmark-v15-retrieval.json`.
This **offline** experiment creates four temporary 14-module Python repositories,
compares lexical vs dependency-aware retrieval under the same file budget,
and scores selected files against predefined task-relevance labels using precision,
recall and F1. It uses no API calls. The generated repositories deliberately
contain import-connected modules and unrelated distractors; these synthetic
results should not be generalized to real-world code-editing success.


## v1.6 feedback-driven repair diagnostics

With `attempts=2` or more, failed smoke, generated, and independent tests
produce bounded, stage-aware feedback for the next implementation attempt.
Each attempt starts from the original repository snapshot, so replacement edit
batches must include all needed changes. Provider errors stop implementation
retries rather than being treated as code defects. The result includes a `repair`
summary with attempted/recovered/code_failures/provider_failures counts.
These diagnostics do not establish that repair improves performance: compare
`attempts=1` and `attempts=3` on identical held-out tasks with independent tests.

### Feedback ablation (v1.7)

Run `python3 benchmarks/v16/repair_experiment.py --mode offline --runs 2 --output benchmark-feedback-offline.json` to validate the three conditions: `single` (one attempt), `resample` (three independent attempts without failure context), and `feedback` (three attempts with diagnostic feedback). Then run `--mode live --runs 2 --cooldown 45 --output benchmark-feedback-live.json` when the provider quota permits. Offline scripted outcomes validate plumbing only; they do not demonstrate model repair. The `resample` condition intentionally uses identical prompt messages on each attempt and retains temperature 0, so repeated outputs may be deterministic. The experiment does not control provider load or random seeds.
