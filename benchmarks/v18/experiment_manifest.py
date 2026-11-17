"""Generate a machine-readable experiment manifest recording runtime, git, model, and fixture provenance."""
import datetime
import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

from benchmarks.v18.task_suite_runner import ROOT, tasks


def get_git_commit() -> str:
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        return res.stdout.strip()
    except Exception:
        return "unknown"


def generate_manifest(output_path: str = "EXPERIMENT_MANIFEST.json") -> dict:
    commit_sha = get_git_commit()
    all_tasks = tasks()

    fixture_digests = {}
    for t in all_tasks:
        tid = t["id"]
        pub_path = ROOT / t["public_verifier"]
        held_path = ROOT / t["heldout_verifier"]
        pub_sha = hashlib.sha256(pub_path.read_bytes()).hexdigest() if pub_path.exists() else None
        held_sha = hashlib.sha256(held_path.read_bytes()).hexdigest() if held_path.exists() else None
        fixture_digests[tid] = {
            "category": t["category"],
            "public_verifier_sha256": pub_sha,
            "heldout_verifier_sha256": held_sha,
        }

    manifest = {
        "manifest_schema": 1,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "git_commit_sha": commit_sha,
        "environment": {
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "system": platform.system(),
            "architecture": platform.machine(),
        },
        "model_configuration": {
            "primary_provider": "groq",
            "model_id": os.environ.get("CODEPILOT_MODEL", "openai/gpt-oss-120b"),
            "temperature_resample": 0.7,
            "temperature_repair": 0.0,
            "format_retries": int(os.environ.get("CODEPILOT_FORMAT_RETRIES", "2")),
            "max_retries": int(os.environ.get("CODEPILOT_MAX_RETRIES", "3")),
        },
        "benchmark_metadata": {
            "suite_version": "v1.8",
            "total_tasks": len(all_tasks),
            "synthetic_algorithmic_tasks": 15,
            "enterprise_distributed_tasks": 7,
            "fixtures": fixture_digests,
        },
        "provenance_definitions": {
            "controlled_reproducible_failure": (
                "The initial attempt is replayed from a deterministic known failed edit "
                "so that all arms evaluate on an identical, leakage-free failure snapshot."
            ),
            "live_recovery_attempts": (
                "Subsequent repair attempts make fresh live model completions through the provider API."
            ),
            "counterfactual_replay_policy": (
                "Executable multi-candidate patch generation evaluated against local test suites "
                "and ranked deterministically without leakage to held-out tests."
            ),
        },
    }

    out_file = Path(output_path)
    out_file.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "EXPERIMENT_MANIFEST.json"
    data = generate_manifest(out)
    print(f"Generated manifest at {out} (Git commit: {data['git_commit_sha']})")
