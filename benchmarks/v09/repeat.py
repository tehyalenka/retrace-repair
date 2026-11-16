"""Repeat the v0.9 benchmark for one- and three-attempt configurations.

Each run starts from the original fixture; live calls use provider quota.
"""
import argparse
import json
import statistics
from pathlib import Path

from evaluate import evaluate

CASES = ("bugfix", "feature", "refactor")


def run_repeated(runs, attempt_limits, output, generated=False, evaluator=evaluate):
    if runs < 1 or not attempt_limits or any(n < 1 or n > 5 for n in attempt_limits):
        raise ValueError("runs must be positive and attempt limits must be between 1 and 5")
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    records = []
    for limit in attempt_limits:
        for index in range(1, runs + 1):
            raw_path = output.with_name("{}-attempts{}-run{}.json".format(output.stem, limit, index))
            report = evaluator(list(CASES), limit, generated, raw_path)
            for case in report["cases"]:
                history = case.get("history", [])
                records.append({"case": case["case"], "attempt_limit": limit,
                                "run": index, "success": bool(case["success"]),
                                "first_attempt_passed": bool(case.get("first_attempt_passed")),
                                "attempts_used": case.get("attempts_used", len(history)),
                                "recovered_after_failure": bool(case["success"] and
                                                                not case.get("first_attempt_passed")),
                                "elapsed_seconds": case["elapsed_seconds"],
                                "error": case.get("error")})
    summaries = []
    for limit in attempt_limits:
        subset = [r for r in records if r["attempt_limit"] == limit]
        count = len(subset)
        summaries.append({"attempt_limit": limit, "tasks_evaluated": count,
                          "successes": sum(r["success"] for r in subset),
                          "success_rate": sum(r["success"] for r in subset) / count,
                          "first_attempt_success_rate": sum(r["first_attempt_passed"] for r in subset) / count,
                          "recovered_after_failure": sum(r["recovered_after_failure"] for r in subset),
                          "mean_attempts_used": round(statistics.mean(r["attempts_used"] for r in subset), 3),
                          "mean_elapsed_seconds": round(statistics.mean(r["elapsed_seconds"] for r in subset), 3)})
    result = {"configuration": {"runs_per_case": runs, "attempt_limits": list(attempt_limits),
                                 "cases": list(CASES), "generated_tests": generated},
              "summary": summaries, "runs": records}
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("Saved {} ({} task evaluations)".format(output, len(records)))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--attempt-limits", type=int, nargs="+", default=[1, 3])
    parser.add_argument("--generate-tests", action="store_true")
    parser.add_argument("--output", default="benchmark-v10-repeat.json")
    args = parser.parse_args()
    run_repeated(args.runs, args.attempt_limits, args.output, args.generate_tests)


if __name__ == "__main__":
    main()
