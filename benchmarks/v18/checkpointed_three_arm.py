"""Checkpointed three-arm paired replay. Offline continuations are scripted.

A saved model completion is persisted before it is returned to the agent.
Do not publish checkpoint files without reviewing embedded prompts/source.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from unittest.mock import patch

from benchmarks.v18 import record_replay as base
from benchmarks.v18.provenance import experiment_provenance
from codepilot.agent import ModelRequestAccounting, ModelRequestBudgetExceeded
from benchmarks.v18.record_replay import _edit

class ProviderBlocked(RuntimeError):
    """Provider rejected a live request; current arm remains resumable."""
    def __init__(self, message, status_code=None, is_transient=None):
        super().__init__(str(message))
        self.message = str(message)
        if status_code is None:
            m = re.search(r"HTTP\s+(\d{3})", self.message)
            if m:
                status_code = int(m.group(1))
        self.status_code = status_code
        if is_transient is not None:
            self.is_transient = bool(is_transient)
        elif self.status_code in (429, 502, 503, 504):
            self.is_transient = True
        elif self.status_code in (400, 401, 403, 404, 422):
            self.is_transient = False
        else:
            lowered = self.message.lower()
            if any(p in lowered for p in ["429", "rate limit", "quota", "too many requests", "503", "504", "resume later", "connection failed", "temporarily unavailable"]):
                self.is_transient = True
            elif any(p in lowered for p in ["401", "403", "unauthorized", "forbidden", "invalid api key", "not found"]):
                self.is_transient = False
            else:
                self.is_transient = False


class BenchmarkBudgetExceeded(RuntimeError):
    """An arm exhausted its durable HTTP request allowance."""


ARMS = (("resample", False, "standard"),
        ("feedback", True, "standard"),
        ("counterfactual", True, "counterfactual"))


def _write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=str(path.parent),
                                     prefix=".checkpoint-", delete=False) as tmp:
        json.dump(value, tmp, indent=2)
        tmp.flush()
        os.fsync(tmp.fileno())
        name = tmp.name
    os.replace(name, path)


def _heldout_check(repo, result, heldout_source):
    """Evaluate final code only, after agent returns; never expose heldout to agent."""
    with tempfile.TemporaryDirectory(prefix="codepilot-heldout-") as tmp:
        workspace = Path(tmp) / "repo"
        shutil.copytree(repo, workspace, ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__", "node_modules", ".env"))
        for name, contents in result.get("files", {}).items():
            target = (workspace / name).resolve()
            if not target.is_relative_to(workspace.resolve()) or target.suffix != ".py":
                raise ValueError("Unsafe final file path")
            if contents is None:
                target.unlink(missing_ok=True)
            else:
                if not target.parent.exists():
                    raise ValueError("Unexpected final file directory")
                target.write_text(contents, encoding="utf-8")
        check = base.agent_module.run_verification(workspace, heldout_source)
        return {"passed": bool(check["passed"]), "tests_run": check["tests_run"],
                "output": check["output"]}


def evaluate(trace_path, output, offline=False, repetitions=1, attempts=3, heldout_verification=None, max_http_requests_per_arm=None, counterfactual_policy=None):
    if counterfactual_policy is None:
        counterfactual_policy = os.environ.get("CODEPILOT_COUNTERFACTUAL_POLICY", "counterfactual")
    active_arms = (
        ("resample", False, "standard"),
        ("feedback", True, "standard"),
        (counterfactual_policy, True, counterfactual_policy),
    )
    if repetitions < 1 or attempts < 2:
        raise ValueError("repetitions must be >=1 and attempts >=2")
    if max_http_requests_per_arm is not None:
        if type(max_http_requests_per_arm) is not int or max_http_requests_per_arm < 0:
            raise ValueError("max_http_requests_per_arm must be a nonnegative integer")
    trace_path = Path(trace_path)
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    first_attempt = trace.get("first_attempt", {})
    if (
        trace.get("schema") != 1
        or first_attempt.get("failure_category") != "test_failure"
        or first_attempt.get("tests_run", 0) < 1
        or "No tests discovered" in str(first_attempt.get("output", ""))
        or "Start directory is not importable" in str(first_attempt.get("output", ""))
    ):
        raise ValueError(
            "A genuine public-test failure with discovered tests is required"
        )
    if not trace.get("calls") or not isinstance(trace["calls"][0].get("response"), str):
        raise ValueError("Missing captured initial completion")
    if offline and trace.get("mode") != "offline":
        raise ValueError("Scripted continuations require an offline trace")
    if heldout_verification is not None:
        if not isinstance(heldout_verification, str) or not heldout_verification.strip():
            raise ValueError("Heldout verifier must be nonempty")
    digest = hashlib.sha256(trace_path.read_bytes()).hexdigest()
    output = Path(output)
    settings = {"trace_sha256": digest, "offline": offline, "repetitions": repetitions,
                "attempts": attempts, "repo_sha256": trace["repo_sha256"],
                "verifier_sha256": trace["verifier_sha256"],
                "counterfactual_policy": counterfactual_policy,
                "active_arms": [list(arm) for arm in active_arms]}
    if heldout_verification is not None:
        settings["heldout_sha256"] = hashlib.sha256(heldout_verification.encode("utf-8")).hexdigest()
    if max_http_requests_per_arm is not None:
        settings["max_http_requests_per_arm"] = max_http_requests_per_arm
    if not offline:
        settings["model_provenance"] = experiment_provenance(offline=False)
    if output.exists():
        report = json.loads(output.read_text(encoding="utf-8"))
        if report.get("settings") != settings:
            raise ValueError("Checkpoint settings or captured trace changed")
        if max_http_requests_per_arm is not None and "request_reservations" not in report:
            if report.get("rows") or report.get("pending"):
                raise ValueError("Existing checkpoint lacks durable request reservations")
    else:
        report = {"schema": 1, "settings": settings, "rows": [], "pending": {},
                  "notice": "Contains prompts and model-generated code; review before sharing."}
    if max_http_requests_per_arm is not None:
        report.setdefault("request_reservations", {})
    with tempfile.TemporaryDirectory() as temp:
        repo, task, verifier = base.task_setup(trace["mode"], trace["case"], temp)
        if base.fingerprint(repo) != trace["repo_sha256"] or task != trace["task"]:
            raise ValueError("Repository/task mismatch")
        if hashlib.sha256(verifier.encode("utf-8")).hexdigest() != trace["verifier_sha256"]:
            raise ValueError("Verifier mismatch")
        real_ask = base.agent_module.ask_model
        for repetition in range(1, repetitions + 1):
            # Rotate execution order across repetitions to reduce order effects.
            arms = list(active_arms)
            arms = arms[(repetition - 1) % 3:] + arms[:(repetition - 1) % 3]
            for condition, feedback, policy in arms:
                key = "{}:{}".format(repetition, condition)
                if any(r["key"] == key for r in report["rows"]):
                    continue
                saved = report["pending"].get(key, [])
                previous_requests = report.get("request_reservations", {}).get(key, 0)
                if type(previous_requests) is not int or previous_requests < 0:
                    raise ValueError("Invalid checkpoint request reservation count")
                if (max_http_requests_per_arm is not None
                        and previous_requests > max_http_requests_per_arm):
                    raise ValueError("Checkpoint exceeds configured request budget")
                index = [0]
                calls = []

                def ask(messages, **kwargs):
                    i = index[0]
                    index[0] += 1
                    request = {
                        "messages": [dict(m) for m in messages],
                        "options": dict(kwargs),
                    }
                    if i < len(saved):
                        previous = saved[i]
                        if previous["request"] != request:
                            raise ValueError("Saved model request differs from replay request")
                        response = previous["response"]
                        origin = "checkpoint_replay"
                    elif i == 0:
                        response = trace["calls"][0]["response"]
                        origin = "captured_initial"
                    elif offline:
                        response = _edit("def double(x):\n    return 2*x\n")
                        origin = "scripted"
                    else:
                        response = real_ask(messages, **kwargs)
                        origin = "live"
                    calls.append({"origin": origin, "request": request, "response": response})
                    if i >= len(saved):
                        saved.append({"request": request, "response": response})
                        report["pending"][key] = saved
                        _write(output, report)  # persist before agent receives response
                    return response

                def reserve_request(next_count):
                    # Persist a conservative reservation before sending HTTP.
                    report["request_reservations"][key] = next_count
                    _write(output, report)

                resample_temp = float(os.environ.get("CODEPILOT_TEMPERATURE_RESAMPLE", "0.7"))
                repair_temp = float(os.environ.get("CODEPILOT_TEMPERATURE_REPAIR", "0.0"))
                seed_base = int(os.environ.get("CODEPILOT_SEED_BASE", "42"))

                arm_temperature = resample_temp if condition == "resample" else (repair_temp if not offline else None)
                arm_seed = (seed_base + repetition * 100) if condition == "resample" else None
                with ModelRequestAccounting(
                    max_http_requests=max_http_requests_per_arm,
                    on_request_reserved=(
                        reserve_request if max_http_requests_per_arm is not None else None
                    ),
                ) as accounting:
                    accounting.http_requests = previous_requests
                    try:
                        with patch.object(base.agent_module, "ask_model", side_effect=ask):
                            result = base.agent_module.run_agent(
                                repo, task, attempts=attempts, verification=verifier,
                                repair_feedback=feedback, repair_policy=policy,
                                temperature=arm_temperature, seed=arm_seed)
                    except ModelRequestBudgetExceeded as exc:
                        raise BenchmarkBudgetExceeded(
                            "HTTP request budget exhausted for arm {}".format(key)
                        ) from exc
                provider_errors = [h for h in result.get("history", [])
                                   if h.get("failure_stage") == "model_request"
                                   and h.get("failure_category") == "provider_error"]
                if provider_errors and not offline:
                    # Keep the captured initial and any successful responses in pending.
                    # Never count a provider outage as a failed repair.
                    _write(output, report)
                    last_err = provider_errors[-1]
                    err_output = str(last_err.get("output", "Provider unavailable"))
                    err_status = last_err.get("status_code")
                    raise ProviderBlocked(err_output, status_code=err_status)
                history = result.get("history") or []
                first_replayed = history[0] if history else {}
                if (
                    first_replayed.get("failure_category") != "test_failure"
                    or first_replayed.get("tests_run", 0) < 1
                    or "No tests discovered" in str(first_replayed.get("output", ""))
                    or "Start directory is not importable" in str(first_replayed.get("output", ""))
                ):
                    raise ValueError(
                        "First-attempt public-test failure was not genuinely reproduced"
                    )
                heldout = _heldout_check(repo, result, heldout_verification) if heldout_verification is not None else None
                report["rows"].append({"key": key, "repetition": repetition,
                                       "condition": condition, "success": bool(result["success"]),
                                       "history": result["history"], "heldout": heldout, "calls": calls,
                                       "live_calls": sum(c["origin"] == "live" for c in calls),
                                      "completion_origins": {
                                          origin: sum(c["origin"] == origin for c in calls)
                                          for origin in (
                                              "captured_initial",
                                              "checkpoint_replay",
                                              "scripted",
                                              "live",
                                          )
                                      },
                                      "request_accounting": accounting.snapshot()})
                report["pending"].pop(key, None)
                _write(output, report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--max-http-requests-per-arm", type=int, default=None)
    args = parser.parse_args()
    result = evaluate(
        args.trace, args.output, args.offline, args.repetitions, args.attempts,
        max_http_requests_per_arm=args.max_http_requests_per_arm,
    )
    print("Completed {} arms; saved {}".format(len(result["rows"]), args.output))


if __name__ == "__main__":
    main()
