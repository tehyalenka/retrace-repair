"""Generate a machine-readable experiment manifest recording runtime, git, model, input, and artifact provenance."""
import datetime
import hashlib
import json
import os
import platform
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Dict, Optional

from benchmarks.v18.task_suite_runner import ROOT, tasks


def get_git_commit() -> str:
    """Resolve current Git HEAD, falling back to direct .git ref parsing if git CLI is unavailable."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception:
        pass

    try:
        git_dir = ROOT.parent.parent / ".git" if not (ROOT / ".git").exists() else ROOT / ".git"
        if not git_dir.exists():
            # Check current working directory
            git_dir = Path(".git")
        if (git_dir / "HEAD").exists():
            head = (git_dir / "HEAD").read_text(encoding="utf-8").strip()
            if head.startswith("ref: "):
                ref_path = git_dir / head[5:]
                if ref_path.exists():
                    return ref_path.read_text(encoding="utf-8").strip()
            return head
    except Exception:
        pass
    return "unknown"


def is_git_dirty() -> Optional[bool]:
    """Check if git working tree has uncommitted modifications."""
    try:
        res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if res.returncode == 0:
            return len(res.stdout.strip()) > 0
    except Exception:
        pass
    return None


def hash_directory_files(directory: Path) -> Dict[str, str]:
    """Compute sha256 digests for all files relative to a directory."""
    digests = {}
    if not directory.exists() or not directory.is_dir():
        return digests
    for p in sorted(directory.rglob("*")):
        if p.is_file():
            rel = str(p.relative_to(directory))
            digests[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return digests


def generate_manifest(
    output_path: str = "EXPERIMENT_MANIFEST.json",
    results_dir: Optional[str] = None,
    evaluation_commit_sha: Optional[str] = None,
    run_id: Optional[str] = None,
) -> dict:
    current_commit = get_git_commit()
    dirty = is_git_dirty()
    all_tasks = tasks()

    # Cryptographic input sealing: hash prompts, verifiers, seed repos, and reference solutions
    task_input_hashes = {}
    for t in all_tasks:
        tid = t["id"]
        pub_path = ROOT / t["public_verifier"]
        held_path = ROOT / t["heldout_verifier"]
        repo_path = ROOT / t["repo"]
        sol_path = ROOT / t["solution"]

        pub_sha = hashlib.sha256(pub_path.read_bytes()).hexdigest() if pub_path.exists() else None
        held_sha = hashlib.sha256(held_path.read_bytes()).hexdigest() if held_path.exists() else None
        prompt_sha = hashlib.sha256(t["task"].encode("utf-8")).hexdigest()
        repo_hashes = hash_directory_files(repo_path)
        sol_hashes = hash_directory_files(sol_path)

        task_input_hashes[tid] = {
            "category": t["category"],
            "task_prompt_sha256": prompt_sha,
            "public_verifier_sha256": pub_sha,
            "heldout_verifier_sha256": held_sha,
            "seed_repo_files_sha256": repo_hashes,
            "reference_solution_files_sha256": sol_hashes,
        }

    # Hash output evaluation artifacts if directory provided
    artifact_hashes = {}
    if results_dir:
        res_path = Path(results_dir)
        if res_path.exists():
            for p in sorted(res_path.glob("*.json")):
                if p.is_file():
                    artifact_hashes[p.name] = hashlib.sha256(p.read_bytes()).hexdigest()

    manifest = {
        "manifest_schema": 2,
        "run_id": run_id or str(uuid.uuid4()),
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "git_provenance": {
            "evaluation_commit_sha": evaluation_commit_sha or current_commit,
            "reporting_commit_sha": current_commit,
            "working_tree_dirty": dirty,
        },
        "environment": {
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "system": platform.system(),
            "architecture": platform.machine(),
        },
        "model_configuration": {
            "primary_provider": os.environ.get("CODEPILOT_PROVIDER", "groq"),
            "model_id": os.environ.get("CODEPILOT_MODEL", "openai/gpt-oss-120b"),
            "temperature_resample": 0.7,
            "temperature_repair": 0.0,
            "seed_base": 42,
            "format_retries": int(os.environ.get("CODEPILOT_FORMAT_RETRIES", "2")),
            "max_retries": int(os.environ.get("CODEPILOT_MAX_RETRIES", "3")),
        },
        "benchmark_metadata": {
            "suite_version": "v1.8",
            "total_tasks": len(all_tasks),
            "synthetic_algorithmic_tasks": 15,
            "enterprise_distributed_tasks": 7,
            "task_inputs": task_input_hashes,
        },
        "artifact_hashes": artifact_hashes,
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
            "security_execution_boundary": (
                "Workspace edit containment and atomic rollback safety. Runtime execution occurs in disposable "
                "temporary directories without network access during replay, but kernel-level OS sandboxing "
                "(seccomp/containers) is not yet active."
            ),
        },
    }

    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "EXPERIMENT_MANIFEST.json"
    target_res = sys.argv[2] if len(sys.argv) > 2 else "research-full-suite-22"
    data = generate_manifest(output_path=out, results_dir=target_res)
    print(f"Generated manifest schema v2 at {out}")
    print(f"Evaluation commit: {data['git_provenance']['evaluation_commit_sha']}")
    print(f"Working tree dirty: {data['git_provenance']['working_tree_dirty']}")
