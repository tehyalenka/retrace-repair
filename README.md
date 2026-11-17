# RETRACE

**Repository-aware program repair with test feedback and experimental replay evaluations.**

RETRACE (formerly CodePilot-X) is an experimental Python coding-agent research prototype. It retrieves relevant repository context, requests structured edits from a hosted language model, validates the proposed edit batch, runs tests against a temporary copy, and returns the proposed files and attempt history. **It does not modify the original repository.**

> **Research status:** The project contains historical experiments and benchmark scripts concerning repair feedback, checkpoints, and replay. A controlled *counterfactual replay* capability that executes and compares alternative repair policies from an identical checkpoint is **not yet established as an integrated agent feature**. Do not interpret the project name as a measured research result.

## Quickstart

Requires Python 3.9+ and, for live model runs, an API key for the selected provider.

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e .
python3 -m unittest discover -s tests -v
python3 -m codepilot.cli map examples/sample_repo
python3 -m codepilot.cli search examples/sample_repo 'fix authentication'
```

To run the agent (uses provider API quota):

```bash
export CODEPILOT_PROVIDER=groq
export GROQ_API_KEY='YOUR_KEY_HERE'
python3 -m codepilot.cli agent examples/sample_repo \
  'Make username matching case-insensitive while preserving password validation' \
  --attempts 2 --output codepilot-result.json
```

Review the output JSON before using any proposed edits. Never commit API keys or `.env` files. OpenAI is also supported via `CODEPILOT_PROVIDER=openai` and `OPENAI_API_KEY`.

**Naming transition:** The public project name is RETRACE. The current Python distribution, `codepilot` import/CLI, and `CODEPILOT_*` environment variables remain unchanged for compatibility. A separate, tested package rename is planned; this README does not pretend it has happened.

## How it works

```text
Repository → AST inventory + retrieval → model-proposed JSON edit batch
           → validate paths / operations / syntax → disposable workspace
           → repository unittest tests (+ optional verification)
           → success report OR bounded failure feedback and another attempt
```

The agent supports multi-file Python edits, including supported create/modify/delete operations. Attempts restart from the original repository snapshot, so a retry must return a complete replacement edit batch. Optional model-generated verification tests are experimental and **not independent of the model**. Independently authored external tests offer a stronger evaluation signal.

The FastAPI backend and Angular frontend provide a local research dashboard. They are not a security boundary and should not be exposed publicly with code execution enabled.

## Evidence and reproducibility

The original project README reported these **historical user-observed synthetic results**. They have not been independently rerun or audited for this documentation update.

| Experiment | Reported outcome | Interpretation |
| --- | --- | --- |
| v0.3 single-file pilot | 3/3 tasks | Small synthetic pilot |
| v0.4 corrected pilot | 20/20 tasks | Single-run synthetic tasks |
| v0.5 paired comparison | 4/4 completed comparisons | Fifth task aborted; no demonstrated improvement |
| v0.5.1 injected faults | 5/5 detected and repaired | Hand-authored checks; no baseline comparison |
| v0.6 multi-file pilot | 9/9 in both conditions | Ceiling result; no separation between conditions |

**No validated real-repository success rate, confidence interval, or token-cost comparison is claimed here.** The feedback ablation defines `single`, `resample`, and `feedback` conditions, but the original README did not report comparable live outcome numbers. Its documented resample baseline uses repeated identical prompts at temperature 0, so it should not be interpreted as an independent stochastic resampling control.

Offline evaluation entry points include:

```bash
python3 benchmarks/v15/evaluate.py --max-files 2 --output benchmark-v15-retrieval.json
python3 benchmarks/v16/repair_experiment.py --mode offline --runs 2 --output benchmark-feedback-offline.json
```

These synthetic/offline checks exercise experimental plumbing, **not autonomous repair performance**. For a publishable comparison, use held-out real-repository tasks, fixed task snapshots, independent tests, a documented sampling policy, paired budgets, per-task request/token cost, and uncertainty intervals. Preserve raw JSON artifacts and record model/provider/settings.

## Limitations and security

- **Not a sandbox.** Generated code and tests may execute locally with your privileges. Use trusted repositories only; do not expose execution endpoints to the public internet.
- Passing tests does not establish functional correctness or generalization.
- The implementation primarily uses complete-file Python edits; large patches and non-Python projects are outside its established scope.
- Retrieval and test discovery are limited by repository structure and supported tooling; `unittest` is the core execution path.
- Model-generated verification is not independent; benchmark evaluation should use separately authored, hidden tests.
- Synthetic benchmark outcomes are not evidence of SWE-bench or production performance.
- Live runs depend on model/provider availability, quotas, sampling behavior, and reproducibility settings.

## Repository layout

| Path | Purpose |
| --- | --- |
| `src/codepilot/` | Agent, repository analyzer, CLI (legacy internal name) |
| `backend/` | FastAPI local dashboard backend |
| `frontend/` | Angular dashboard |
| `tests/` | Python regression tests |
| `benchmarks/` | Experimental evaluations and artifacts |
| `scripts/` | Earlier evaluation and utility scripts |
| `examples/` | Sample repositories |
| `CHANGELOG.md` | Historical milestones and known evidence gaps |

## Development roadmap

1. Audit replay/checkpoint benchmark code and specify a reproducible counterfactual branch interface.
2. Add paired policy comparisons with independent tests and budget accounting.
3. Repair the stochastic resample control and collect real-repository benchmark results.
4. Add CI, choose a license, and migrate package/import/environment names with compatibility tests.
5. Isolate untrusted code execution before public interactive deployment.

## License

**No license has been selected yet.** Public GitHub visibility does not grant a general license to reuse the code. A license should be added only after the repository owner chooses its terms.
