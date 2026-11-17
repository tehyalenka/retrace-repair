"""A/B comparison of lexical and dependency-aware retrieval on v1.1 tasks."""
import argparse
import json
import sys
import time
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "src"))
from codepilot.agent import run_agent

CASES = ("bugfix", "feature", "refactor")


def _provider_failure(record):
    """Identify infrastructure failures even when they occur during format repair."""
    for item in record.get("history", []):
        if item.get("failure_category") == "provider_error":
            return True
        if "LLM API HTTP 429" in item.get("output", ""):
            return True
    return "LLMAPIError" in record.get("error", "")


def evaluate(runs, attempts, max_files, output_dir, agent=run_agent,
             cooldown=0.0, sleep=time.sleep):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    tasks = json.loads((HERE / "tasks.json").read_text(encoding="utf-8"))
    records = []
    for run in range(1, runs + 1):
        # Alternate strategy order to reduce order-related rate-limit bias.
        strategies = ("lexical", "dependency") if run % 2 else ("dependency", "lexical")
        for strategy in strategies:
            for case in CASES:
                if records and cooldown:
                    sleep(cooldown)
                start = time.monotonic()
                try:
                    result = agent(str(HERE / "cases" / case), tasks[case],
                                   attempts=attempts, max_files=max_files,
                                   verification=(HERE / "hidden" / (case + ".py")).read_text(encoding="utf-8"),
                                   retrieval_strategy=strategy)
                    history = result.get("history", [])
                    record = {"run": run, "strategy": strategy, "case": case,
                              "success": bool(result["success"]),
                              "attempts_used": len(history),
                              "first_attempt_passed": bool(history and history[0].get("passed")),
                              "history": history,
                              "retrieval": result.get("retrieval", {}),
                              "elapsed_seconds": round(time.monotonic() - start, 3)}
                except Exception as exc:
                    record = {"run": run, "strategy": strategy, "case": case,
                              "success": False, "attempts_used": 0,
                              "first_attempt_passed": False,
                              "error": "{}: {}".format(type(exc).__name__, exc),
                              "elapsed_seconds": round(time.monotonic() - start, 3)}
                record["infrastructure_failure"] = _provider_failure(record)
                records.append(record)
                print("{} run {} {}: {}".format(strategy, run, case,
                      "PASS" if record["success"] else "FAIL"), flush=True)
    summary = []
    for strategy in ("lexical", "dependency"):
        subset = [r for r in records if r["strategy"] == strategy]
        completed = [r for r in subset if not r["infrastructure_failure"]]
        n = len(subset)
        m = len(completed)
        summary.append({"strategy": strategy, "tasks": n,
                        "successes": sum(r["success"] for r in subset),
                        "success_rate": sum(r["success"] for r in subset) / n if n else 0,
                        "infrastructure_failures": n - m,
                        "completed_tasks": m,
                        "completed_success_rate": sum(r["success"] for r in completed) / m if m else None,
                        "first_attempt_success_rate": sum(r["first_attempt_passed"] for r in subset) / n if n else 0,
                        "mean_task_seconds": round(sum(r["elapsed_seconds"] for r in subset) / n, 3) if n else 0,
                        "mean_completed_seconds": round(sum(r["elapsed_seconds"] for r in completed) / m, 3) if m else None})
    report = {"configuration": {"runs_per_strategy": runs, "attempts": attempts,
              "max_files": max_files, "cooldown_seconds": cooldown, "cases": list(CASES)},
              "summary": summary, "runs": records,
              "note": "Completed-task success excludes infrastructure failures; do not compare without considering exclusions."}
    (output_dir / "comparison.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--attempts", type=int, default=1)
    parser.add_argument("--max-files", type=int, default=6)
    parser.add_argument("--output-dir", default="benchmark-v14-retrieval")
    parser.add_argument("--cooldown", type=float, default=30.0, help="Seconds between task API requests")
    args = parser.parse_args()
    if args.runs < 1 or not 1 <= args.attempts <= 5 or args.max_files < 1 or args.cooldown < 0:
        parser.error("runs/max-files must be positive and attempts must be 1-5")
    evaluate(args.runs, args.attempts, args.max_files, args.output_dir, cooldown=args.cooldown)


if __name__ == "__main__":
    main()
