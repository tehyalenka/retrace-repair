# CodePilot-X — GitHub release guide

## Project overview

CodePilot-X is an experimental repository-aware Python coding agent with an Angular dashboard and FastAPI backend. It indexes repository source, proposes complete-file Python edits through a hosted language model, runs tests against temporary repository copies, and records attempts and repair diagnostics. The original repository is not automatically modified by the agent.

## Verified local checks (16 November 2026)

- Python regression suite: **152 tests, OK** (31.282 seconds), reported from the project virtual environment.
- Public smoke-test fixtures: **15/15** reference solutions pass public and independent heldout checks; the initial broken implementations fail public checks as designed.
- Mocked backend integration: **4/4** tests passed; covers repository reads, path traversal rejection, mocked run lifecycle/artifacts, and provider errors.
- Angular 17 production build and development server compile successfully.
- Angular dashboard displays repository data from FastAPI. Browser run/repair-history rendering has **not** been verified end-to-end.

These are local observations, not an independently reproduced production audit.

## Setup

Prerequisites: Python 3.9+, Node.js compatible with Angular 17 (Node 18.13+ or supported Node 20), npm, and an API key only for live agent runs.

```bash
cd CodePilot-X
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m pip install fastapi uvicorn
CODEPILOT_MAX_RETRIES=3 CODEPILOT_FORMAT_RETRIES=2 PYTHONPATH=src:. \
  python -m unittest discover -s tests -p 'test_*.py' -q
```

In separate terminals, start the API and dashboard:

```bash
# From CodePilot-X, with .venv active
PYTHONPATH=src:. python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

```bash
cd frontend
npm ci
npm start
```

Visit `http://127.0.0.1:4200` and `http://127.0.0.1:8000/docs`. The frontend dev server proxies `/api` to port 8000.

## Benchmark validation (offline)

```bash
PYTHONPATH=src:. python -m benchmarks.v18.task_suite_runner validate
PYTHONPATH=src:. python -m unittest tests.test_v18_public_smoke -v
PYTHONPATH=src:. python -m unittest tests.test_offline_dashboard_integration -v
```

The benchmark contains 15 synthetic tasks across bugfix, feature, refactor, multifile and regression categories. Public tests guide repairs; heldout tests provide a separate correctness check. Fixture validation does **not** measure autonomous model success.

## Research evaluation status

Three conditions are under study: **resample** (retry without diagnostic feedback), **feedback** (retry using failure diagnostics), and **counterfactual** (paired repair variant). The intended design has 15 tasks × 3 arms = 45 evaluations. A previous run was interrupted by provider HTTP 429 errors, leaving 4 completed and 41 pending. Those completed rows also contained public-test infrastructure warnings, so their outcomes must not be interpreted as reliable arm success rates. The public-test fixture infrastructure was subsequently fixed and validated offline.

Do **not** merge old captures/checkpoints with new post-fix results. Keep historical output separate. When quota is available, use a **new** output directory and run a small smoke evaluation first. Live runs incur API costs and execute generated code; review the benchmark scripts and safety implications before enabling them.

Research report command (for an existing results directory):

```bash
PYTHONPATH=src:. python -m benchmarks.v18.research_report \
  --results-dir v18-task-suite-results \
  --output-dir v18-task-suite-results/research
```

## Security and limitations

- **Not a sandbox**: generated code and repository tests may execute with the current user's permissions. Only run on trusted repositories and review code and diffs.
- Do not upload proprietary code or credentials without permission. Never commit `.env`, API keys, run traces containing sensitive prompts, or private repositories.
- Agent edits are restricted to existing Python files and complete-file replacements; retrieval and verification have limitations.
- Synthetic tasks and offline mocked tests are not evidence of general software engineering capability or superiority of one repair strategy.
- Provider rate limits and nondeterminism can affect live experiments. Record environment, model, parameters, and failures.

## Project organization

- `src/codepilot/`: Python agent, retrieval and CLI
- `backend/`: FastAPI dashboard endpoints
- `frontend/`: Angular dashboard
- `benchmarks/`: experimental harnesses and synthetic fixtures
- `tests/`: unit and integration tests

For prior-version historical details, see the existing root `README.md`. This guide is a release companion, not a replacement for historical research records.
