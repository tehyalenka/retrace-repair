"""Compare one attempt, repeated sampling, and diagnostic-feedback repair.

Offline mode demonstrates measurement plumbing; it is NOT evidence of model capability.
Live mode uses the v1.1 tasks and their independent verification tests.
"""
import argparse
import json
import sys
import time
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from codepilot.agent import run_agent

HERE = ROOT / "benchmarks" / "v11"
CASES = ("bugfix", "feature", "refactor")


def offline_fixture(path):
    path.mkdir(parents=True, exist_ok=True)
    (path / "calc.py").write_text("def double(x):\n    return x\n", encoding="utf-8")
    tests = path / "tests"
    tests.mkdir()
    (tests / "test_smoke.py").write_text(
        "import unittest\nfrom calc import double\nclass Smoke(unittest.TestCase):\n"
        "    def test_zero(self): self.assertEqual(double(0), 0)\n", encoding="utf-8")
    verifier = ("import unittest\nfrom calc import double\nclass Verify(unittest.TestCase):\n"
                "    def test_positive(self): self.assertEqual(double(3), 6)\n")
    return verifier


def _edit(source):
    return json.dumps({"edits": [{"path": "calc.py", "operation": "modify", "content": source}]})


def run(mode="offline", runs=2, cooldown=0, output="benchmark-v16-repair.json", agent=run_agent):
    if mode not in ("offline", "live"):
        raise ValueError("mode must be offline or live")
    if runs < 1 or cooldown < 0:
        raise ValueError("runs must be positive and cooldown nonnegative")
    import tempfile
    tasks = json.loads((HERE / "tasks.json").read_text(encoding="utf-8")) if mode == "live" else {}
    records = []
    for repeat in range(1, runs + 1):
        conditions = (("single", 1, False), ("resample", 3, False), ("feedback", 3, True))
        if repeat % 2 == 0:
            conditions = tuple(reversed(conditions))
        for condition, max_attempts, use_feedback in conditions:
            names = CASES if mode == "live" else ("scripted_verification_failure",)
            for name in names:
                started = time.monotonic()
                try:
                    if mode == "offline":
                        with tempfile.TemporaryDirectory() as tmp:
                            repo = Path(tmp) / "repo"
                            verification = offline_fixture(repo)
                            answers = [_edit("def double(x):\n    return x\n"),
                                       _edit("def double(x):\n    return 2*x\n")]
                            with patch("codepilot.agent.ask_model", side_effect=answers):
                                result = agent(repo, "double values", attempts=max_attempts,
                                               verification=verification, repair_feedback=use_feedback)
                    else:
                        verification = (HERE / "hidden" / (name + ".py")).read_text(encoding="utf-8")
                        result = agent(HERE / "cases" / name, tasks[name], attempts=max_attempts,
                                       verification=verification, repair_feedback=use_feedback)
                    history = result.get("history", [])
                    first = bool(history and history[0].get("passed"))
                    infra = any(h.get("failure_category") == "provider_error" for h in history)
                    code_failures = sum(h.get("failure_category") == "test_failure" for h in history)
                    records.append({"run": repeat, "condition": condition, "feedback_enabled": use_feedback, "attempt_limit": max_attempts, "case": name,
                                    "success": bool(result.get("success")), "first_attempt_passed": first,
                                    "recovered_code_failure": bool(result.get("success") and code_failures),
                                    "code_failures": code_failures, "infrastructure_failure": infra,
                                    "attempts_used": len(history), "history": history,
                                    "elapsed_seconds": round(time.monotonic()-started, 3)})
                except Exception as exc:
                    records.append({"run": repeat, "condition": condition, "feedback_enabled": use_feedback, "attempt_limit": max_attempts, "case": name,
                                    "success": False, "infrastructure_failure": False,
                                    "harness_error": type(exc).__name__ + ": " + str(exc),
                                    "elapsed_seconds": round(time.monotonic()-started, 3)})
                print("run {} condition {} {}: {}".format(repeat, condition, name,
                      "PASS" if records[-1]["success"] else "FAIL"), flush=True)
                if cooldown:
                    time.sleep(cooldown)
    summary = {}
    for condition in ("single", "resample", "feedback"):
        rows = [r for r in records if r["condition"] == condition]
        completed = [r for r in rows if not r.get("infrastructure_failure") and not r.get("harness_error")]
        summary[condition] = {"total": len(rows), "successes": sum(r["success"] for r in rows),
                               "infrastructure_failures": sum(r.get("infrastructure_failure", False) for r in rows),
                               "harness_errors": sum(bool(r.get("harness_error")) for r in rows),
                               "completed": len(completed),
                               "completed_success_rate": (sum(r["success"] for r in completed) / len(completed)
                                                          if completed else None),
                               "recovered_code_failures": sum(r.get("recovered_code_failure", False) for r in rows),
                               "mean_elapsed_seconds": round(sum(r["elapsed_seconds"] for r in rows) / len(rows), 3)
                               if rows else None}
    report = {"configuration": {"mode": mode, "runs": runs, "cooldown": cooldown,
                                "conditions": {"single": {"attempts": 1, "feedback": False}, "resample": {"attempts": 3, "feedback": False}, "feedback": {"attempts": 3, "feedback": True}}}, "summary": summary, "runs": records,
              "limitations": ["Offline responses are scripted; do not use as evidence of LLM repair ability",
                              "Live runs are subject to model variance and provider availability",
                              "Repeated sampling and feedback use the same attempt budget, but model randomness and provider failures remain confounders"]}
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("offline", "live"), default="offline")
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--cooldown", type=float, default=0)
    parser.add_argument("--output", default="benchmark-v16-repair.json")
    args = parser.parse_args()
    run(args.mode, args.runs, args.cooldown, args.output)
    print("Saved " + args.output)


if __name__ == "__main__":
    main()
