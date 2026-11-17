"""Autonomous benchmark runner with automatic rate-limit backoff and final reporting.

Monitors checkpoint progress, handles HTTP 429 provider rate limits with exponential
or interval backoff, resumes safely from checkpoints, and automatically compiles
the research gate audit, metrics, and report upon completion.
"""

import argparse
import datetime
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Collection, Dict, List, Optional, Set

from codepilot.agent import LLMAPIError
from benchmarks.v18 import task_suite_runner
from benchmarks.v18.checkpointed_three_arm import ProviderBlocked
from benchmarks.v18.task_suite_runner import summarize


def is_valid_evaluation_row(row: Dict[str, Any], condition: str, repetition: int) -> bool:
    """Validate that a benchmark row represents a legitimate terminal evaluation result.

    Checks:
    1. Condition and repetition consistency (including agreement with row['key'] if present).
    2. Exact condition identity: strictly rejects policy substitution between 'counterfactual' and 'counterfactual_replay'.
    3. Terminal public-test outcome ('success' present and is a boolean).
    4. Terminal held-out outcome ('heldout' present, is a dict, with boolean 'passed').
    5. Terminal execution evidence (presence of NON-EMPTY 'history', 'calls', or 'request_accounting').
    """
    if not isinstance(row, dict):
        return False

    # Safely validate repetition value
    rep_val = row.get("repetition")
    if rep_val is None:
        key = row.get("key")
        if isinstance(key, str) and ":" in key:
            parts = key.split(":", 1)
            if parts[0].isdigit():
                rep_val = int(parts[0])
    if not isinstance(rep_val, int) or rep_val != repetition:
        return False

    # Strict condition identity: reject any cross-policy substitution
    cond_val = row.get("condition")
    if cond_val is None:
        key = row.get("key")
        if isinstance(key, str) and ":" in key:
            cond_val = key.split(":", 1)[1]
    if cond_val != condition:
        return False

    # Key consistency if key is present
    key = row.get("key")
    if key and isinstance(key, str):
        expected_key = f"{repetition}:{condition}"
        if key != expected_key:
            return False

    if "success" not in row or not isinstance(row["success"], bool):
        return False

    heldout = row.get("heldout")
    if not isinstance(heldout, dict) or "passed" not in heldout or not isinstance(heldout["passed"], bool):
        return False

    # Non-empty execution evidence (must not be empty containers)
    history = row.get("history")
    has_history = isinstance(history, list) and len(history) > 0

    calls = row.get("calls")
    has_calls = isinstance(calls, list) and len(calls) > 0

    req_acc = row.get("request_accounting")
    has_accounting = isinstance(req_acc, dict) and len(req_acc) > 0 and (
        req_acc.get("http_requests", 0) > 0
        or req_acc.get("logical_calls", 0) > 0
        or req_acc.get("usage_reports", 0) > 0
        or req_acc.get("prompt_tokens") is not None
    )

    if not (has_history or has_calls or has_accounting):
        return False

    return True


def check_benchmark_matrix(
    output_dir: Path,
    target_tasks: Optional[List[Dict[str, Any]]] = None,
    repetitions: int = 1,
    required_policies: Optional[Collection[str]] = None,
) -> Dict[str, Any]:
    """Strictly evaluates progress across the task-policy-repetition experiment matrix."""
    policies = set(required_policies) if required_policies else {"resample", "feedback", "counterfactual"}

    if target_tasks is not None:
        target_task_ids = [t["id"] for t in target_tasks]
    else:
        # Discover task IDs from *-live.json files present in output directory
        discovered = [f.stem.replace("-live", "") for f in sorted(output_dir.glob("*-live.json"))]
        target_task_ids = discovered if discovered else []

    total_expected_cells = len(target_task_ids) * len(policies) * repetitions
    completed_cells = 0
    fully_completed_tasks = []
    incomplete_tasks = []

    for task_id in target_task_ids:
        live_file = output_dir / f"{task_id}-live.json"
        if not live_file.exists():
            incomplete_tasks.append(task_id)
            continue
        try:
            data = json.loads(live_file.read_text(encoding="utf-8"))
        except Exception:
            incomplete_tasks.append(task_id)
            continue

        if data.get("pending"):
            incomplete_tasks.append(task_id)
            continue

        rows = data.get("rows", [])
        completed_for_task = set()
        for r in rows:
            if not isinstance(r, dict):
                continue

            cond = r.get("condition")
            if not cond and "key" in r and isinstance(r["key"], str):
                parts = r["key"].split(":")
                if len(parts) == 2:
                    cond = parts[1]

            rep_raw = r.get("repetition")
            if rep_raw is None and "key" in r and isinstance(r["key"], str):
                parts = r["key"].split(":")
                if len(parts) == 2 and parts[0].isdigit():
                    rep_raw = parts[0]
            try:
                rep = int(rep_raw) if rep_raw is not None else 1
            except (ValueError, TypeError):
                continue

            # Strict policy match: NEVER substitute replay for prompt or vice versa
            if cond in policies and 1 <= rep <= repetitions:
                if is_valid_evaluation_row(r, cond, rep):
                    completed_for_task.add((cond, rep))

        completed_cells += len(completed_for_task)
        if len(completed_for_task) >= len(policies) * repetitions:
            fully_completed_tasks.append(task_id)
        else:
            incomplete_tasks.append(task_id)

    is_complete = bool(target_task_ids) and (len(fully_completed_tasks) == len(target_task_ids)) and (completed_cells >= total_expected_cells)
    return {
        "is_complete": is_complete,
        "completed_tasks_count": len(fully_completed_tasks),
        "total_tasks_count": len(target_task_ids),
        "completed_matrix_cells": completed_cells,
        "total_matrix_cells": total_expected_cells,
        "completed_task_ids": fully_completed_tasks,
        "incomplete_task_ids": incomplete_tasks,
    }


def get_completed_tasks_count(
    output_dir: Path,
    total_tasks: int = 22,
    target_tasks: Optional[List[Dict[str, Any]]] = None,
    repetitions: int = 1,
) -> int:
    """Backward-compatible helper returning fully completed tasks satisfying matrix criteria."""
    res = check_benchmark_matrix(output_dir, target_tasks=target_tasks, repetitions=repetitions)
    return res["completed_tasks_count"]


def is_benchmark_complete(
    output_dir: Path,
    total_tasks: int = 22,
    target_tasks: Optional[List[Dict[str, Any]]] = None,
    repetitions: int = 1,
) -> bool:
    """Verify whether all target tasks have satisfied all matrix policy-repetition combinations."""
    res = check_benchmark_matrix(output_dir, target_tasks=target_tasks, repetitions=repetitions)
    if total_tasks and res["completed_tasks_count"] < total_tasks:
        return False
    return res["is_complete"]


def run_post_benchmark_pipeline(output_dir: Path, target_total: int = 22, run_manifest_path: Optional[Path] = None):
    print("\n" + "=" * 70, flush=True)
    print(f"ALL {target_total} TARGET TASKS COMPLETED! Running post-benchmark pipeline...", flush=True)
    print("=" * 70, flush=True)

    errors = []

    # 1. Summarize and generate benchmark-proof.json
    print("\n[1/5] Generating final summary and cryptographic proof...", flush=True)
    try:
        summarize(str(output_dir))
    except Exception as exc:
        errors.append(f"Summary generation failed: {exc}")

    # 2. Run research gate
    print("\n[2/5] Auditing evidence with Research Gate...", flush=True)
    try:
        from benchmarks.v18 import research_gate
        gate_report = research_gate.evaluate_directory(str(output_dir))
        gate_path = output_dir / "research-gate-verdict.json"
        gate_path.write_text(json.dumps(gate_report, indent=2), encoding="utf-8")
        print(f"Research Gate report saved to {gate_path}", flush=True)
    except Exception as exc:
        errors.append(f"Research Gate audit failed: {exc}")

    # 3. Generate research report and metrics
    print("\n[3/5] Generating research report and metrics...", flush=True)
    try:
        from benchmarks.v18 import research_report
        report_dir = output_dir / "research"
        report_dir.mkdir(parents=True, exist_ok=True)
        research_report.generate(str(output_dir), str(report_dir))
        print(f"Research report compiled in {report_dir}", flush=True)
    except Exception as exc:
        errors.append(f"Research Report generation failed: {exc}")

    # 4. Run statistical analysis and paired McNemar tests
    print("\n[4/5] Computing statistical significance (McNemar) & token accounting...", flush=True)
    try:
        from benchmarks.v18 import statistical_analysis
        stats_report = statistical_analysis.analyze_directory(str(output_dir))
        stats_path = output_dir / "statistical-analysis-report.json"
        stats_path.write_text(json.dumps(stats_report, indent=2), encoding="utf-8")
        print(f"Statistical analysis report saved to {stats_path}", flush=True)
    except Exception as exc:
        errors.append(f"Statistical Analysis failed: {exc}")

    # 5. Seal post-execution evidence manifest
    print("\n[5/5] Cryptographically sealing output evidence manifest...", flush=True)
    try:
        from benchmarks.v18.experiment_manifest import seal_evidence_manifest
        manifest_p = run_manifest_path or (output_dir / "run-manifest.json")
        if not manifest_p.exists():
            raise FileNotFoundError(f"Required run manifest {manifest_p} not found; cannot seal evidence.")
        evidence = seal_evidence_manifest(output_dir, manifest_p)
        print(
            f"Evidence sealed in {output_dir / 'evidence-manifest.json'} "
            f"({evidence['total_artifacts_sealed']} artifacts)",
            flush=True,
        )
    except Exception as exc:
        errors.append(f"Evidence manifest seal failed: {exc}")

    if errors:
        print("\n" + "!" * 70, flush=True)
        print("FAIL-CLOSED ALERT: Post-benchmark pipeline encountered critical error(s):", flush=True)
        for e in errors:
            print(f"  - {e}", flush=True)
        print("!" * 70 + "\n", flush=True)
        raise RuntimeError(f"Post-benchmark evidence pipeline failed: {'; '.join(errors)}")

    print("\n" + "=" * 70, flush=True)
    print("AUTONOMOUS BENCHMARK RUNNER FINISHED SUCCESSFULLY.", flush=True)
    print("=" * 70 + "\n", flush=True)


def main():
    parser = argparse.ArgumentParser(
        description="Autonomous benchmark executor with 429 rate limit backoff and report generation."
    )
    parser.add_argument("--output-dir", default="research-full-suite-22")
    parser.add_argument(
        "--category",
        choices=["bugfix", "feature", "refactor", "multifile", "regression", "enterprise"],
        default=None,
    )
    parser.add_argument("--tasks", default=None, help="Comma-separated task IDs")
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--attempts", type=int, default=2)
    parser.add_argument("--delay-seconds", type=float, default=2.0)
    parser.add_argument(
        "--retry-interval-seconds",
        type=int,
        default=240,
        help="Seconds to wait between retry cycles when quota is exceeded (default: 240s = 4m)",
    )
    parser.add_argument(
        "--max-hours",
        type=float,
        default=24.0,
        help="Maximum hours to wait before giving up (default: 24h)",
    )
    parser.add_argument(
        "--temperature-resample",
        type=float,
        default=0.7,
        help="Resample baseline temperature (default: 0.7)",
    )
    parser.add_argument(
        "--temperature-repair",
        type=float,
        default=0.0,
        help="Repair agent temperature (default: 0.0)",
    )
    parser.add_argument(
        "--seed-base",
        type=int,
        default=42,
        help="Seed base for reproducible resample (default: 42)",
    )
    parser.add_argument(
        "--counterfactual-policy",
        choices=["counterfactual", "counterfactual_replay"],
        default="counterfactual",
        help="Counterfactual arm policy: 'counterfactual' (prompt guidance) or 'counterfactual_replay' (executable search)",
    )
    parser.add_argument(
        "--policies",
        default=None,
        help="Comma-separated required policies for matrix completion (default: derived dynamically from arms)",
    )
    args = parser.parse_args()

    # Synchronize runner configuration with environment variables consumed by model request handlers
    os.environ["CODEPILOT_TEMPERATURE_RESAMPLE"] = str(args.temperature_resample)
    os.environ["CODEPILOT_TEMPERATURE_REPAIR"] = str(args.temperature_repair)
    os.environ["CODEPILOT_SEED_BASE"] = str(args.seed_base)
    os.environ["CODEPILOT_COUNTERFACTUAL_POLICY"] = args.counterfactual_policy

    # Derive the required policy set dynamically from configuration (Finding 2)
    if args.policies:
        required_policies = [p.strip() for p in args.policies.split(",") if p.strip()]
    else:
        required_policies = ["resample", "feedback", args.counterfactual_policy]

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest_file = Path("benchmarks/v18/task_suite/manifest.json")
    with open(manifest_file, "r", encoding="utf-8") as f:
        manifest_data = json.load(f)["tasks"]

    if args.category:
        target_tasks = [t for t in manifest_data if t.get("category") == args.category]
    elif args.tasks:
        target_ids = {t.strip() for t in args.tasks.split(",") if t.strip()}
        target_tasks = [t for t in manifest_data if t.get("id") in target_ids]
    else:
        target_tasks = manifest_data
    total_target_count = len(target_tasks)

    task_ids_set = {t["id"] for t in target_tasks} if (args.category or args.tasks) else None

    # Assemble effective runtime configuration (strictly reflecting actual model call settings)
    effective_config = {
        "output_dir": str(out_dir),
        "category": args.category,
        "tasks": args.tasks,
        "repetitions": args.repetitions,
        "attempts": args.attempts,
        "delay_seconds": args.delay_seconds,
        "retry_interval_seconds": args.retry_interval_seconds,
        "max_hours": args.max_hours,
        "primary_provider": os.environ.get("CODEPILOT_PROVIDER", "groq"),
        "model_id": os.environ.get("CODEPILOT_MODEL", "openai/gpt-oss-120b"),
        "temperature_resample": args.temperature_resample,
        "temperature_repair": args.temperature_repair,
        "seed_base": args.seed_base,
        "counterfactual_policy": args.counterfactual_policy,
        "required_policies": list(required_policies),
    }

    # Lifecycle Stage 1: Pre-run manifest initialization and fail-closed resume validation
    run_manifest_path = out_dir / "run-manifest.json"
    from benchmarks.v18.experiment_manifest import generate_run_manifest, verify_run_manifest

    if run_manifest_path.exists():
        try:
            verify_run_manifest(run_manifest_path, current_config=effective_config, task_list=target_tasks)
            print(f"Verified existing run-manifest on resume: {run_manifest_path}", flush=True)
        except Exception as exc:
            print("\n" + "!" * 70, flush=True)
            print(f"CRITICAL INTEGRITY ERROR: Manifest validation failed on resume: {exc}", flush=True)
            print("Aborting autonomous execution to preserve experiment provenance (fail-closed).", flush=True)
            print("!" * 70 + "\n", flush=True)
            sys.exit(1)
    else:
        try:
            generate_run_manifest(run_manifest_path, config=effective_config, task_list=target_tasks)
            print(f"Pre-run manifest initialized at: {run_manifest_path}", flush=True)
        except Exception as exc:
            print("\n" + "!" * 70, flush=True)
            print(f"CRITICAL INTEGRITY ERROR: Failed to initialize pre-run manifest: {exc}", flush=True)
            print("Aborting autonomous execution: pre-run provenance snapshot is required (fail-closed).", flush=True)
            print("!" * 70 + "\n", flush=True)
            sys.exit(1)

    start_time = time.time()
    max_wait_seconds = args.max_hours * 3600
    cycle = 0

    print("=" * 70, flush=True)
    print(f"RETRACE AUTONOMOUS BENCHMARK RUNNER", flush=True)
    print(f"Started at: {datetime.datetime.now(datetime.timezone.utc).isoformat()}", flush=True)
    print(f"Output Directory: {out_dir}", flush=True)
    print(f"Target Tasks: {total_target_count} tasks (Category: {args.category or 'all'})", flush=True)
    print(f"Check interval on 429: {args.retry_interval_seconds}s", flush=True)
    print(f"Max wait time: {args.max_hours} hours", flush=True)
    print("=" * 70, flush=True)

    while True:
        cycle += 1
        elapsed = time.time() - start_time
        if elapsed > max_wait_seconds:
            print(f"Max wait time ({args.max_hours}h) exceeded. Exiting.", flush=True)
            sys.exit(1)

        matrix_status = check_benchmark_matrix(
            out_dir,
            target_tasks=target_tasks,
            repetitions=args.repetitions,
            required_policies=required_policies,
        )
        completed_tasks = matrix_status["completed_tasks_count"]
        print(
            f"\n[Cycle {cycle} | {datetime.datetime.now().strftime('%H:%M:%S')}] "
            f"Progress: {completed_tasks}/{total_target_count} tasks complete "
            f"({matrix_status['completed_matrix_cells']}/{matrix_status['total_matrix_cells']} matrix evaluations).",
            flush=True,
        )

        if matrix_status["is_complete"]:
            run_post_benchmark_pipeline(out_dir, target_total=total_target_count, run_manifest_path=run_manifest_path)
            sys.exit(0)

        # Run live suite
        try:
            task_suite_runner.run_live(
                output_dir=str(out_dir),
                repetitions=args.repetitions,
                attempts=args.attempts,
                delay_seconds=args.delay_seconds,
                category=args.category,
                task_ids=task_ids_set,
                counterfactual_policy=args.counterfactual_policy,
            )
        except Exception as exc:
            # Typed provider-error classification (Finding 3)
            is_typed_provider_error = isinstance(exc, (LLMAPIError, ProviderBlocked))
            http_status = getattr(exc, "status_code", None)
            is_transient_status = http_status in (429, 503, 504)
            is_transient_os_network = isinstance(exc, (IOError, OSError)) and any(
                phrase in str(exc).lower() for phrase in ["429", "too many requests", "rate limit"]
            )
            is_transient = is_typed_provider_error or is_transient_status or is_transient_os_network

            if is_transient:
                print(
                    f"\n[Cycle {cycle}] Transient provider quota/rate limit encountered ({type(exc).__name__}): {exc}. "
                    f"Will back off and retry.",
                    flush=True,
                )
            else:
                print("\n" + "!" * 70, flush=True)
                print(f"FATAL NON-TRANSIENT BENCHMARK ERROR ({type(exc).__name__}): {exc}", flush=True)
                print("Aborting autonomous execution immediately (fail-closed).", flush=True)
                print("!" * 70 + "\n", flush=True)
                raise exc

        # Check matrix again if complete
        matrix_status = check_benchmark_matrix(
            out_dir,
            target_tasks=target_tasks,
            repetitions=args.repetitions,
            required_policies=required_policies,
        )
        if matrix_status["is_complete"]:
            run_post_benchmark_pipeline(out_dir, target_total=total_target_count, run_manifest_path=run_manifest_path)
            sys.exit(0)

        print(
            f"Provider quota or rate limit currently active "
            f"({matrix_status['completed_tasks_count']}/{total_target_count} tasks finished, "
            f"{matrix_status['completed_matrix_cells']}/{matrix_status['total_matrix_cells']} evaluations). "
            f"Sleeping for {args.retry_interval_seconds}s before next autonomous retry...",
            flush=True,
        )
        time.sleep(args.retry_interval_seconds)


if __name__ == "__main__":
    main()
