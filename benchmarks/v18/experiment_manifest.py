"""Lifecycle-aware experiment manifest generator and evidence sealer for RETRACE benchmarks.

Maintains two immutable provenance records per evaluation:
1. run-manifest.json: Pre-run snapshot containing effective configuration, Git provenance, and input fixture hashes.
   Validated on resume to guarantee configuration consistency across interruptions.
2. evidence-manifest.json: Post-run evidence seal capturing SHA-256 digests of all generated artifacts
   and cryptographically referencing the original run manifest.
"""
import datetime
import hashlib
import json
import logging
import os
import platform
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from benchmarks.v18.task_suite_runner import ROOT, tasks

logger = logging.getLogger("retrace.manifest")


def resolve_git_dir(base: Path) -> Path:
    """Resolve .git directory, following gitdir pointers for worktrees or submodules."""
    p = base / ".git"
    if p.is_file():
        try:
            content = p.read_text(encoding="utf-8").strip()
            if content.startswith("gitdir:"):
                target = content.split(":", 1)[1].strip()
                return (base / target).resolve()
        except Exception:
            pass
    return p


def get_git_provenance() -> Tuple[str, Optional[bool], str, bool]:
    """Resolve Git commit SHA, working tree cleanliness, method, and publication grade status.
    
    Returns:
        (commit_sha, working_tree_dirty, resolution_method, publication_grade)
    """
    # 1. Try Git CLI
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if res.returncode == 0 and res.stdout.strip():
            sha = res.stdout.strip()
            dirty = None
            try:
                stat = subprocess.run(
                    ["git", "status", "--porcelain"],
                    cwd=str(ROOT),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                if stat.returncode == 0:
                    dirty = len(stat.stdout.strip()) > 0
            except Exception:
                pass
            is_pub_grade = bool(len(sha) == 40 and dirty is False)
            return sha, dirty, "git_cli", is_pub_grade
    except Exception:
        pass

    # 2. Filesystem fallback: direct inspection of gitdir
    git_dir = resolve_git_dir(ROOT)
    if not git_dir.exists():
        # Try checking parent repository root
        git_dir = resolve_git_dir(Path("."))

    if git_dir.exists():
        head_file = git_dir / "HEAD"
        if head_file.exists():
            try:
                content = head_file.read_text(encoding="utf-8").strip()
                if not content.startswith("ref: "):
                    # Detached HEAD (raw commit hash)
                    sha = content
                    return sha, None, "detached_head_file", False
                
                ref = content[5:].strip()
                ref_file = git_dir / ref
                if ref_file.exists():
                    sha = ref_file.read_text(encoding="utf-8").strip()
                    return sha, None, "loose_ref_file", False

                # Check packed-refs
                packed = git_dir / "packed-refs"
                if packed.exists():
                    for line in packed.read_text(encoding="utf-8").splitlines():
                        line = line.strip()
                        if line and not line.startswith("#") and not line.startswith("^"):
                            parts = line.split()
                            if len(parts) == 2 and parts[1] == ref:
                                return parts[0], None, "packed_refs_file", False

                # Check reflog
                reflog = git_dir / "logs" / "HEAD"
                if reflog.exists():
                    lines = reflog.read_text(encoding="utf-8").splitlines()
                    if lines:
                        parts = lines[-1].split()
                        if len(parts) >= 2 and len(parts[1]) == 40:
                            return parts[1], None, "reflog_file", False
            except Exception as exc:
                logger.warning("Error reading git refs from filesystem: %s", exc)

    return "unknown", None, "unverified_fallback", False


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


def compute_task_input_hashes(task_list: Optional[List[Dict]] = None) -> Dict[str, Dict]:
    """Compute cryptographic SHA-256 digests for all benchmark task inputs."""
    all_tasks = task_list if task_list is not None else tasks()
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
    return task_input_hashes


def hash_output_artifacts(results_dir: Path) -> Dict[str, str]:
    """Compute sha256 digests for all output artifact JSON files."""
    artifact_hashes = {}
    if results_dir.exists():
        for p in sorted(results_dir.glob("*.json")):
            if p.is_file() and not p.name.endswith("-manifest.json"):
                artifact_hashes[p.name] = hashlib.sha256(p.read_bytes()).hexdigest()
    return artifact_hashes


def generate_run_manifest(
    output_path: Path,
    config: Optional[Dict[str, Any]] = None,
    task_list: Optional[List[Dict]] = None,
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate and save the immutable pre-run manifest before benchmark execution."""
    sha, dirty, method, pub_grade = get_git_provenance()
    effective_config = {
        "primary_provider": os.environ.get("CODEPILOT_PROVIDER", "groq"),
        "model_id": os.environ.get("CODEPILOT_MODEL", "openai/gpt-oss-120b"),
        "temperature_resample": 0.7,
        "temperature_repair": 0.0,
        "seed_base": 42,
        "format_retries": int(os.environ.get("CODEPILOT_FORMAT_RETRIES", "2")),
        "max_retries": int(os.environ.get("CODEPILOT_MAX_RETRIES", "3")),
    }
    if config:
        effective_config.update(config)

    task_inputs = compute_task_input_hashes(task_list)
    manifest_id = run_id or str(uuid.uuid4())

    manifest = {
        "manifest_schema": 3,
        "lifecycle_stage": "pre_run_snapshot",
        "run_id": manifest_id,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "git_provenance": {
            "commit_sha": sha,
            "working_tree_dirty": dirty,
            "resolution_method": method,
            "publication_grade": pub_grade,
        },
        "environment": {
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "system": platform.system(),
            "architecture": platform.machine(),
        },
        "effective_configuration": effective_config,
        "benchmark_metadata": {
            "suite_version": "v1.8",
            "total_tasks": len(task_inputs),
            "task_inputs": task_inputs,
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
            "security_execution_boundary": (
                "Workspace edit containment and atomic rollback safety. Replay evaluations use offline "
                "test fixtures in disposable working directories. Network isolation is not enforced at the "
                "operating-system level, and untrusted code execution requires additional sandboxing."
            ),
        },
    }

    manifest_bytes = json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8")
    manifest["run_manifest_sha256"] = hashlib.sha256(manifest_bytes).hexdigest()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def verify_run_manifest(
    run_manifest_path: Path,
    current_config: Optional[Dict[str, Any]] = None,
    task_list: Optional[List[Dict]] = None,
) -> bool:
    """Verify that current configuration and task input hashes match a saved run-manifest upon resume."""
    if not run_manifest_path.exists():
        raise FileNotFoundError(f"Run manifest not found at {run_manifest_path}")

    data = json.loads(run_manifest_path.read_text(encoding="utf-8"))
    saved_inputs = data.get("benchmark_metadata", {}).get("task_inputs", {})
    current_inputs = compute_task_input_hashes(task_list)

    # Validate task input hashes
    for tid, saved_t in saved_inputs.items():
        if tid in current_inputs:
            cur_t = current_inputs[tid]
            if saved_t.get("public_verifier_sha256") != cur_t.get("public_verifier_sha256"):
                raise ValueError(f"Task input mismatch on resume: public verifier changed for task '{tid}'")
            if saved_t.get("heldout_verifier_sha256") != cur_t.get("heldout_verifier_sha256"):
                raise ValueError(f"Task input mismatch on resume: heldout verifier changed for task '{tid}'")
            if saved_t.get("task_prompt_sha256") != cur_t.get("task_prompt_sha256"):
                raise ValueError(f"Task input mismatch on resume: prompt text changed for task '{tid}'")

    # Validate effective model configuration and policy sets if provided (fail-closed on drift)
    if current_config:
        saved_config = data.get("effective_configuration", {})
        for key in ["model_id", "primary_provider", "temperature_resample", "temperature_repair"]:
            if key in current_config and key in saved_config:
                if str(current_config[key]) != str(saved_config[key]):
                    raise ValueError(
                        f"Configuration drift detected on resume: {key} changed from {saved_config[key]} to {current_config[key]}"
                    )
        if "required_policies" in current_config and "required_policies" in saved_config:
            if set(current_config["required_policies"]) != set(saved_config["required_policies"]):
                raise ValueError(
                    f"Policy set drift on resume: expected {saved_config['required_policies']} but got {current_config['required_policies']}"
                )

    return True


def seal_evidence_manifest(
    results_dir: Path,
    run_manifest_path: Path,
    output_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Seal post-execution evidence by hashing all produced artifacts and referencing run-manifest."""
    if not run_manifest_path.exists():
        raise FileNotFoundError(f"Run manifest {run_manifest_path} must exist to seal evidence.")

    run_manifest = json.loads(run_manifest_path.read_text(encoding="utf-8"))
    artifact_hashes = hash_output_artifacts(results_dir)
    sha, dirty, method, pub_grade = get_git_provenance()

    seal_file = output_path or (results_dir / "evidence-manifest.json")
    evidence = {
        "manifest_schema": 3,
        "lifecycle_stage": "post_run_evidence_seal",
        "run_id": run_manifest.get("run_id"),
        "run_manifest_sha256": run_manifest.get("run_manifest_sha256"),
        "sealed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "git_provenance": {
            "execution_commit_sha": run_manifest.get("git_provenance", {}).get("commit_sha"),
            "reporting_commit_sha": sha,
            "working_tree_dirty": dirty,
            "resolution_method": method,
            "publication_grade": pub_grade,
        },
        "environment": run_manifest.get("environment"),
        "effective_configuration": run_manifest.get("effective_configuration"),
        "benchmark_metadata": {
            "suite_version": "v1.8",
            "total_tasks": run_manifest.get("benchmark_metadata", {}).get("total_tasks"),
            "task_inputs": run_manifest.get("benchmark_metadata", {}).get("task_inputs"),
        },
        "output_artifacts": artifact_hashes,
        "total_artifacts_sealed": len(artifact_hashes),
    }

    evidence_bytes = json.dumps(evidence, indent=2, sort_keys=True).encode("utf-8")
    evidence["evidence_seal_sha256"] = hashlib.sha256(evidence_bytes).hexdigest()

    seal_file.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    return evidence


# Backwards compatibility function
def generate_manifest(
    output_path: str = "EXPERIMENT_MANIFEST.json",
    results_dir: Optional[str] = None,
    evaluation_commit_sha: Optional[str] = None,
    run_id: Optional[str] = None,
) -> dict:
    """Generate standard unified manifest for compatibility."""
    out_p = Path(output_path)
    res_dir = Path(results_dir) if results_dir else out_p.parent
    run_man = generate_run_manifest(out_p, run_id=run_id)
    if results_dir and Path(results_dir).exists():
        evidence = seal_evidence_manifest(res_dir, out_p, output_path=out_p)
        return evidence
    return run_man


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "EXPERIMENT_MANIFEST.json"
    target_res = sys.argv[2] if len(sys.argv) > 2 else "research-full-suite-22"
    data = generate_manifest(output_path=out, results_dir=target_res)
    print(f"Generated manifest schema v3 at {out}")
    print(f"Commit: {data['git_provenance'].get('commit_sha') or data['git_provenance'].get('execution_commit_sha')}")
    print(f"Method: {data['git_provenance'].get('resolution_method')}")
