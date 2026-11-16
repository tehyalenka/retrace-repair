"""Three-arm CodePilot-X evaluation. Use trusted Python repositories only.

Manifest: {"tasks": [{"id": "bug1", "repository": "/absolute/path",
"task": "...", "verification_file": "/absolute/path/to/hidden_test.py"}]}
Verification files are read by the runner, never included in the model prompt.
"""
import argparse
import hashlib
import json
import os
import random
import time
from pathlib import Path

from codepilot.agent import run_agent

ARMS = {"resample": {"repair_feedback": False, "repair_policy": "standard"},
        "standard": {"repair_feedback": True, "repair_policy": "standard"},
        "counterfactual": {"repair_feedback": True, "repair_policy": "counterfactual"}}


def summarize(rows):
    output = {}
    for arm in ARMS:
        samples = [r for r in rows if r["arm"] == arm]
        eligible = [r for r in samples if r.get("initial_failure_category") not in (None, "provider_error") and not r.get("error")]
        recovered = [r for r in eligible if r["success"]]
        output[arm] = {"runs": len(samples), "successes": sum(bool(r.get("success")) for r in samples),
                       "success_rate": sum(bool(r.get("success")) for r in samples) / len(samples) if samples else None,
                       "initially_failed_eligible": len(eligible), "recovered": len(recovered),
                       "repair_recovery_rate": len(recovered) / len(eligible) if eligible else None,
                       "mean_attempts": sum(r.get("attempts", 0) for r in samples) / len(samples) if samples else None,
                       "elapsed_seconds": round(sum(r.get("elapsed_seconds", 0) for r in samples), 3),
                       "infrastructure_errors": sum(bool(r.get("error")) or r.get("initial_failure_category") == "provider_error" for r in samples)}
    return output


def evaluate(manifest, output, attempts=3, repetitions=1, seed=42):
    tasks = manifest.get("tasks", [])
    if not tasks or len({t["id"] for t in tasks}) != len(tasks):
        raise ValueError("Provide nonempty tasks with unique IDs")
    for task in tasks:
        if not all(task.get(k) for k in ("id", "repository", "task", "verification_file")):
            raise ValueError("Each task needs id, repository, task, verification_file")
        if not Path(task["repository"]).is_dir() or not Path(task["verification_file"]).is_file():
            raise ValueError("Repository or independent verifier missing for " + task["id"])
    config = {"attempts": attempts, "repetitions": repetitions, "seed": seed,
              "tasks": [{"id": t["id"], "repository": str(Path(t["repository"]).resolve()),
                         "task": t["task"], "verifier_sha256": hashlib.sha256(Path(t["verification_file"]).read_bytes()).hexdigest()} for t in tasks]}
    if output.exists():
        previous = json.loads(output.read_text())
        if previous.get("config") != config:
            raise ValueError("Existing output has different configuration; use another output file")
        rows = previous["results"]
    else:
        rows = []
    completed = {(r["task_id"], r["repetition"], r["arm"]) for r in rows}
    rng = random.Random(seed)
    for repetition in range(1, repetitions + 1):
        for task in tasks:
            arms = list(ARMS)
            rng.shuffle(arms)
            for arm in arms:
                if (task["id"], repetition, arm) in completed:
                    continue
                started = time.monotonic()
                row = {"task_id": task["id"], "repetition": repetition, "arm": arm}
                try:
                    result = run_agent(task["repository"], task["task"], attempts=attempts,
                                       verification=Path(task["verification_file"]).read_text(),
                                       **ARMS[arm])
                    history = result.get("history", [])
                    row.update(success=bool(result["success"]), attempts=len(history),
                               first_attempt_passed=bool(history and history[0].get("passed")),
                               initial_failure_category=history[0].get("failure_category") if history else "missing_history",
                               failure_categories=[r.get("failure_category") for r in history if not r.get("passed")],
                               history=history)
                except Exception as exc:
                    row.update(success=False, error="{}: {}".format(type(exc).__name__, str(exc)[:500]))
                row["elapsed_seconds"] = round(time.monotonic() - started, 3)
                rows.append(row)
                report = {"config": config, "results": rows, "summary": summarize(rows),
                          "limitations": "Each arm independently samples its initial edit; repair recovery denominators may differ. Model randomness and task sample size affect conclusions. Token counts are unavailable."}
                output.parent.mkdir(parents=True, exist_ok=True)
                tmp = output.with_suffix(output.suffix + ".tmp")
                tmp.write_text(json.dumps(report, indent=2))
                os.replace(tmp, output)
                print("{} repetition {} {}: {}".format(task["id"], repetition, arm, "PASS" if row["success"] else "FAIL"), flush=True)
    return {"config": config, "results": rows, "summary": summarize(rows)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, default=Path("counterfactual-evaluation.json"))
    parser.add_argument("--attempts", type=int, default=3, choices=range(1, 6))
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if args.repetitions < 1:
        parser.error("--repetitions must be positive")
    report = evaluate(json.loads(args.manifest.read_text()), args.output, args.attempts, args.repetitions, args.seed)
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()
