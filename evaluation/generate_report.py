"""Generate reproducible reports from saved CodePilot-X runs."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def generate_report(root, run_id):
    root = Path(root).resolve()

    if (
        len(run_id) != 12
        or any(c not in "0123456789abcdef" for c in run_id)
    ):
        raise ValueError("Invalid run ID")

    metadata_path = root / ".codepilot-runs" / run_id / "run.json"

    if not metadata_path.is_file():
        raise FileNotFoundError("Saved run not found: " + run_id)

    run = json.loads(metadata_path.read_text(encoding="utf-8"))
    result = run.get("result") or {}
    history = result.get("history") or []

    last = history[-1] if history else {}

    provider_failures = [
        record for record in history
        if record.get("failure_category") == "provider_error"
    ]

    coding_failures = [
        record for record in history
        if record.get("failure_category") == "test_failure"
    ]

    if not history:
        outcome = "not_evaluated"
    elif result.get("success") is True:
        if (
            last.get("passed") is True
            and isinstance(last.get("tests_run"), int)
            and last["tests_run"] > 0
        ):
            outcome = "smoke_tests_passed"
        else:
            outcome = "reported_success_unverified"
    elif last.get("failure_category") == "provider_error":
        outcome = "provider_failure"
    elif last.get("failure_category") == "test_failure":
        outcome = "agent_test_failure"
    else:
        outcome = "agent_failure"


    verification_path = metadata_path.parent / "verification.json"
    saved_verification = None

    if verification_path.is_file():
        saved_verification = json.loads(
            verification_path.read_text(encoding="utf-8")
        )

    verification_passed = (
        saved_verification.get("passed") is True
        and saved_verification.get("returncode") == 0
        and saved_verification.get("timed_out") is False
        if saved_verification is not None
        else None
    )

    # The saved run alone does not establish autonomous provenance.
    if saved_verification is not None and verification_passed is False:
        outcome = "independent_verification_failed"
    elif outcome in ("smoke_tests_passed", "reported_success_unverified"):
        if verification_passed is True:
            outcome = "independent_verification_passed"

    report = {
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repository": run.get("repository"),
        "task": run.get("task"),
        "status": run.get("status"),
        "outcome": outcome,
        "success": result.get("success"),
        "attempts_used": len(history),
        "first_attempt_passed": (
            history[0].get("passed") is True if history else None
        ),
        "files_modified": sorted(result.get("files") or {}),
        "provider": run.get("provider"),
        "model": run.get("model"),
        "retrieval": result.get("retrieval"),
        "provider_failure_count": len(provider_failures),
        "coding_failure_count": len(coding_failures),
        "last_failure_stage": last.get("failure_stage"),
        "last_failure_category": last.get("failure_category"),
        "smoke_tests": {
            "passed": last.get("smoke_tests_passed"),
            "tests_run": last.get("smoke_tests_run"),
        },
        "independent_verification": {
            "passed": verification_passed,
            "returncode": (
                saved_verification.get("returncode")
                if saved_verification is not None else None
            ),
            "timed_out": (
                saved_verification.get("timed_out")
                if saved_verification is not None else None
            ),
            "applied_files": (
                saved_verification.get("applied_files")
                if saved_verification is not None else None
            ),
            "output": (
                saved_verification.get("output")
                if saved_verification is not None
                else last.get("verification_output")
            ),
        },
        "execution_provenance": run.get("execution_provenance") or {
            "source": "unknown",
            "execution_mode": "unknown",
            "recorded_at_creation": False
        },
        "history": [
            {
                "attempt": record.get("attempt"),
                "passed": record.get("passed"),
                "changed_files": record.get("changed_files", []),
                "failure_stage": record.get("failure_stage"),
                "failure_category": record.get("failure_category"),
                "elapsed_seconds": record.get("elapsed_seconds"),
            }
            for record in history
        ],
    }

    output = root / "evaluation" / "reports" / (
        "run-" + run_id + ".json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, default=str) + "\n",
        encoding="utf-8",
    )

    return output, report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--root", default=".")
    args = parser.parse_args()

    output, report = generate_report(args.root, args.run_id)

    print("PASS: Report generated")
    print("File:", output)
    print("Outcome:", report["outcome"])
    print("Attempts:", report["attempts_used"])
    print("Files:", report["files_modified"])
