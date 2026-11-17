"""Repeated, order-balanced seeded-repair evaluation (not natural-error repair)."""
import argparse
import json
import random
from datetime import datetime, timezone
from pathlib import Path

from benchmarks.v19.seeded_repair import SEEDS, run_case


def summarize(cases):
    summary = {}
    for condition in ("resample", "feedback"):
        rows = [r for case in cases for r in case["rows"] if r["condition"] == condition]
        completed = [r for r in rows if not r["provider_failure"]]
        summary[condition] = {
            "trials": len(rows),
            "provider_failures": sum(r["provider_failure"] for r in rows),
            "successful_repairs": sum(r["success"] for r in completed),
            "completed_trials": len(completed),
            "success_rate_completed": (sum(r["success"] for r in completed) / len(completed)) if completed else None,
            "fresh_model_calls": sum(r["fresh_model_calls"] for r in rows),
        }
    return summary


def evaluate(mode="offline", cases=None, repeats=2, attempts=3, seed=2026, output=None):
    if repeats < 1 or attempts < 2:
        raise ValueError("repeats >= 1 and attempts >= 2 required")
    names = list(cases or sorted(SEEDS))
    rng = random.Random(seed)
    jobs = [(case, trial) for trial in range(1, repeats + 1) for case in names]
    rng.shuffle(jobs)
    report = {"schema": 2, "evaluation": "seeded_failure_repeated", "mode": mode,
              "created_utc": datetime.now(timezone.utc).isoformat(),
              "random_seed": seed, "repeats": repeats, "attempts": attempts,
              "cases": [], "errors": [], "summary": {},
              "limitations": ["Seeded errors, not spontaneous model errors",
                              "Offline repairs are scripted, not model-generated",
                              "Small samples and provider errors limit inference",
                              "Only three synthetic task families are represented"]}
    def save():
        report["summary"] = summarize(report["cases"])
        if output:
            dest = Path(output)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(json.dumps(report, indent=2), encoding="utf-8")
    for case, trial in jobs:
        # Alternate the first arm per task and repetition to reduce order effects.
        order = ("resample", "feedback") if (trial + names.index(case)) % 2 else ("feedback", "resample")
        try:
            result = run_case(case, offline=(mode == "offline"), attempts=attempts, condition_order=order)
            result["trial"] = trial
            result["condition_order"] = list(order)
            report["cases"].append(result)
            print("{} trial {}: {}".format(case, trial, ", ".join("{}={}".format(r["condition"], r["success"]) for r in result["rows"])), flush=True)
        except Exception as exc:
            report["errors"].append({"case": case, "trial": trial, "error_type": type(exc).__name__, "message": str(exc)})
            print("{} trial {}: ERROR {}".format(case, trial, type(exc).__name__), flush=True)
        finally:
            save()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("offline", "live"), default="offline")
    parser.add_argument("--cases", nargs="+", choices=sorted(SEEDS), default=sorted(SEEDS))
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--output", default="v20-results.json")
    args = parser.parse_args()
    report = evaluate(args.mode, args.cases, args.repeats, args.attempts, args.seed, args.output)
    print("Summary:", json.dumps(report["summary"], indent=2))
    print("Errors:", len(report["errors"]))
    print("Saved:", args.output)


if __name__ == "__main__":
    main()
