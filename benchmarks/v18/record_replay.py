"""Capture a failed first model edit, then run paired repair arms from that edit.

Offline mode uses scripted corrections and only validates the harness.
Live paired trials make fresh provider calls for the SECOND attempt onward.
Never commit traces containing private repository source or prompts.
"""
import argparse
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
import codepilot.agent as agent_module
def offline_fixture(path):
    path.mkdir(parents=True, exist_ok=True)
    (path / "calc.py").write_text("def double(x):\n    return x\n", encoding="utf-8")
    tests = path / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    (tests / "test_smoke.py").write_text(
        "import unittest\nfrom calc import double\nclass Smoke(unittest.TestCase):\n"
        "    def test_zero(self): self.assertEqual(double(0), 0)\n", encoding="utf-8")
    verifier = ("import unittest\nfrom calc import double\nclass Verify(unittest.TestCase):\n"
                "    def test_positive(self): self.assertEqual(double(3), 6)\n")
    return verifier


def _edit(source):
    return json.dumps({"edits": [{"path": "calc.py", "operation": "modify", "content": source}]})


HERE = ROOT / "benchmarks" / "archive" / "v11"
if not HERE.exists():
    HERE = ROOT / "benchmarks" / "v11"


def fingerprint(repo):
    """Hash all tracked input Python sources, including test fixtures."""
    digest = hashlib.sha256()
    for path in sorted(Path(repo).rglob("*.py")):
        if any(part in (".venv", "__pycache__", ".git") for part in path.parts):
            continue
        relative = path.relative_to(repo).as_posix()
        digest.update(relative.encode("utf-8") + b"\0")
        digest.update(path.read_bytes() + b"\0")
    return digest.hexdigest()


def task_setup(mode, case, temp):
    if mode == "offline":
        repo = Path(temp) / "repo"
        verifier = offline_fixture(repo)
        return repo, "double values", verifier
    tasks = json.loads((HERE / "tasks.json").read_text(encoding="utf-8"))
    if case not in tasks:
        raise ValueError("Unknown case: " + case)
    return HERE / "cases" / case, tasks[case], (HERE / "hidden" / (case + ".py")).read_text(encoding="utf-8")


def capture(mode, case, output):
    with tempfile.TemporaryDirectory() as temp:
        repo, task, verifier = task_setup(mode, case, temp)
        original_ask = agent_module.ask_model
        calls = []

        def recording_ask(messages, **kwargs):
            request = {
                "messages": [dict(m) for m in messages],
                "options": dict(kwargs),
            }
            try:
                if mode == "offline":
                    response = _edit("def double(x):\n    return x\n")
                else:
                    response = original_ask(messages, **kwargs)
                calls.append({**request, "response": response})
                return response
            except Exception as exc:
                calls.append({**request, "error_type": type(exc).__name__, "error": str(exc)})
                raise

        with patch.object(agent_module, "ask_model", side_effect=recording_ask):
            result = agent_module.run_agent(repo, task, attempts=1, verification=verifier)
        history = result.get("history", [])
        trace = {"schema": 1, "mode": mode, "case": case, "task": task,
                 "repo_sha256": fingerprint(repo),
                 "verifier_sha256": hashlib.sha256(verifier.encode("utf-8")).hexdigest(),
                 "calls": calls, "first_attempt": history[0] if history else None,
                 "capture_success": result.get("success", False),
                 "notice": "Contains prompts and generated code; do not publish without reviewing."}
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_text(json.dumps(trace, indent=2), encoding="utf-8")
        return trace


def paired(trace_path, output, offline=False, include_counterfactual=False):
    trace = json.loads(Path(trace_path).read_text(encoding="utf-8"))
    if trace.get("schema") != 1 or not trace.get("calls"):
        raise ValueError("Unsupported or empty trace")
    if trace.get("first_attempt", {}).get("failure_category") != "test_failure":
        raise ValueError("Trace must contain a genuine first-attempt test failure; capture a different case")
    if trace["calls"][0].get("response") is None:
        raise ValueError("First model request did not produce a response")
    mode = trace["mode"]
    if offline and mode != "offline":
        raise ValueError("Scripted offline continuation only supports offline traces")
    rows = []
    with tempfile.TemporaryDirectory() as temp:
        repo, task, verifier = task_setup(mode, trace["case"], temp)
        if fingerprint(repo) != trace["repo_sha256"] or task != trace["task"]:
            raise ValueError("Repository or task changed since capture")
        if hashlib.sha256(verifier.encode("utf-8")).hexdigest() != trace["verifier_sha256"]:
            raise ValueError("Verifier changed since capture")
        first = trace["calls"][0]["response"]
        real_ask = agent_module.ask_model
        conditions = [("resample", False, "standard"), ("feedback", True, "standard")]
        if include_counterfactual:
            conditions.append(("counterfactual", True, "counterfactual"))
        for condition, feedback, policy in conditions:
            calls = []
            arm_temperature = 0.7 if condition == "resample" else None
            arm_seed = 42 if condition == "resample" else None

            def continuation(messages, **kwargs):
                if not calls:
                    response = first
                    origin = "replayed_initial_edit"
                elif offline:
                    response = _edit("def double(x):\n    return 2*x\n")
                    origin = "scripted_continuation"
                else:
                    response = real_ask(messages, **kwargs)
                    origin = "fresh_model_completion"
                calls.append({"origin": origin, "messages": messages, "response": response})
                return response

            with patch.object(agent_module, "ask_model", side_effect=continuation):
                result = agent_module.run_agent(repo, task, attempts=3, verification=verifier,
                                                repair_feedback=feedback, repair_policy=policy,
                                                temperature=arm_temperature, seed=arm_seed,
                                                replay_on_repair_only=True)
            history = result["history"]
            if not history or history[0].get("failure_category") != "test_failure":
                raise ValueError("Replay did not reproduce original test failure")
            rows.append({"condition": condition, "feedback_enabled": feedback, "repair_policy": policy,
                         "success": result["success"], "history": history,
                         "model_calls": calls,
                         "fresh_model_calls": sum(c["origin"] == "fresh_model_completion" for c in calls),
                         "scripted_continuations": sum(c["origin"] == "scripted_continuation" for c in calls)})
    report = {"schema": 1, "mode": mode, "case": trace["case"],
              "source_trace": str(trace_path), "same_initial_edit": True,
              "rows": rows,
              "limitations": ["A single paired comparison cannot establish statistical significance",
                              "Offline scripted continuation is not evidence of autonomous repair",
                              "The two fresh continuations can still differ due to model/provider variability",
                              "Traces may contain source code and prompts; review before sharing"]}
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    c = sub.add_parser("capture")
    c.add_argument("--mode", choices=("offline", "live"), default="offline")
    c.add_argument("--case", choices=("bugfix", "feature", "refactor"), default="bugfix")
    c.add_argument("--output", default="v18-capture.json")
    p = sub.add_parser("paired")
    p.add_argument("--trace", required=True)
    p.add_argument("--output", default="v18-paired.json")
    p.add_argument("--offline", action="store_true", help="Use scripted second responses; offline traces only")
    p.add_argument("--counterfactual", action="store_true", help="Include third paired counterfactual repair arm")
    args = parser.parse_args()
    if args.command == "capture":
        report = capture(args.mode, args.case, args.output)
        print("Captured: " + str(report["first_attempt"].get("failure_category")))
    else:
        report = paired(args.trace, args.output, args.offline, args.counterfactual)
        print("Paired: " + ", ".join("{}={}".format(r["condition"], r["success"]) for r in report["rows"]))
    print("Saved: " + args.output)


if __name__ == "__main__":
    main()
