"""Compare standard prompting with provider JSON-object mode on identical tasks.

Run configurations sequentially. Results are stochastic and not paired trials.
Only trusted benchmark repositories should be executed.
"""
import argparse
import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "src"))
from codepilot.agent import run_agent
from evaluate import evaluate, CASES


def summarize(report):
    cases = report["cases"]
    attempts = [a for case in cases for a in case.get("history", [])]
    return {
        "tasks": len(cases),
        "successes": sum(bool(c.get("success")) for c in cases),
        "first_attempt_successes": sum(bool(c.get("first_attempt_passed")) for c in cases),
        "malformed_json_attempts": sum(a.get("failure_category") == "malformed_edit_json" for a in attempts),
        "format_retries": sum(a.get("format_retries_used", 0) for a in attempts),
        "format_repairs_succeeded": sum(bool(a.get("format_repair_succeeded")) for a in attempts),
        "mean_task_seconds": round(statistics.mean(c["elapsed_seconds"] for c in cases), 3) if cases else 0,
    }


def run_experiment(runs, attempts, output_dir, modes=(False, True), evaluator=evaluate):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for run in range(1, runs + 1):
        for mode in modes:
            name = "json" if mode else "plain"
            output = output_dir / "{}-run{}.json".format(name, run)
            def configured_agent(repo, task, **kwargs):
                return run_agent(repo, task, json_mode=mode, **kwargs)
            report = evaluator(CASES, attempts, False, output, agent=configured_agent)
            results.append({"mode": name, "run": run, "metrics": summarize(report), "report": str(output)})
    summary = {"configuration": {"runs_per_mode": runs, "attempts": attempts,
                                     "task_names": list(CASES), "generated_tests": False},
               "runs": results}
    (output_dir / "comparison.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--attempts", type=int, default=3, choices=range(1, 6))
    parser.add_argument("--output-dir", default="benchmark-v13-json")
    args = parser.parse_args()
    if not 1 <= args.runs <= 20:
        parser.error("--runs must be between 1 and 20")
    print(json.dumps(run_experiment(args.runs, args.attempts, args.output_dir), indent=2))


if __name__ == "__main__":
    main()
