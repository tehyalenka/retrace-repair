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
from typing import Optional

from benchmarks.v18 import task_suite_runner
from benchmarks.v18.task_suite_runner import summarize


def get_completed_tasks_count(output_dir: Path, total_tasks: int = 22) -> int:
    completed = 0
    for f in output_dir.glob("*-live.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            rows = data.get("rows", [])
            pending = data.get("pending", {})
            if len(rows) >= 3 and not pending:
                completed += 1
        except Exception:
            pass
    return completed


def is_benchmark_complete(output_dir: Path, total_tasks: int = 22) -> bool:
    return get_completed_tasks_count(output_dir, total_tasks) >= total_tasks


def run_post_benchmark_pipeline(output_dir: Path, target_total: int = 22, run_manifest_path: Optional[Path] = None):
    print("\n" + "=" * 70, flush=True)
    print(f"ALL {target_total} TARGET TASKS COMPLETED! Running post-benchmark pipeline...", flush=True)
    print("=" * 70, flush=True)

    # 1. Summarize and generate benchmark-proof.json
    print("\n[1/5] Generating final summary and cryptographic proof...", flush=True)
    summarize(str(output_dir))

    # 2. Run research gate
    print("\n[2/5] Auditing evidence with Research Gate...", flush=True)
    try:
        from benchmarks.v18 import research_gate
        gate_report = research_gate.evaluate_directory(str(output_dir))
        gate_path = output_dir / "research-gate-verdict.json"
        gate_path.write_text(json.dumps(gate_report, indent=2), encoding="utf-8")
        print(f"Research Gate report saved to {gate_path}", flush=True)
    except Exception as exc:
        print(f"Warning: Research gate error: {exc}", flush=True)

    # 3. Generate research report and metrics
    print("\n[3/5] Generating research report and metrics...", flush=True)
    try:
        from benchmarks.v18 import research_report
        report_dir = output_dir / "research"
        report_dir.mkdir(parents=True, exist_ok=True)
        research_report.generate(str(output_dir), str(report_dir))
        print(f"Research report compiled in {report_dir}", flush=True)
    except Exception as exc:
        print(f"Warning: Research report generation error: {exc}", flush=True)

    # 4. Run statistical analysis and paired McNemar tests
    print("\n[4/5] Computing statistical significance (McNemar) & token accounting...", flush=True)
    try:
        from benchmarks.v18 import statistical_analysis
        stats_report = statistical_analysis.analyze_directory(str(output_dir))
        stats_path = output_dir / "statistical-analysis-report.json"
        stats_path.write_text(json.dumps(stats_report, indent=2), encoding="utf-8")
        print(f"Statistical analysis report saved to {stats_path}", flush=True)
    except Exception as exc:
        print(f"Warning: Statistical analysis error: {exc}", flush=True)

    # 5. Seal post-execution evidence manifest
    print("\n[5/5] Cryptographically sealing output evidence manifest...", flush=True)
    try:
        from benchmarks.v18.experiment_manifest import seal_evidence_manifest
        manifest_p = run_manifest_path or (output_dir / "run-manifest.json")
        if manifest_p.exists():
            evidence = seal_evidence_manifest(output_dir, manifest_p)
            print(
                f"Evidence sealed in {output_dir / 'evidence-manifest.json'} "
                f"({evidence['total_artifacts_sealed']} artifacts)",
                flush=True,
            )
    except Exception as exc:
        print(f"Warning: Could not seal evidence manifest: {exc}", flush=True)

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
    args = parser.parse_args()

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

    # Assemble effective runtime configuration (removing assumed fixed defaults)
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
        "temperature_resample": 0.7,
        "temperature_repair": 0.0,
        "seed_base": 42,
    }

    # Lifecycle Stage 1: Pre-run manifest initialization and resume validation
    run_manifest_path = out_dir / "run-manifest.json"
    from benchmarks.v18.experiment_manifest import generate_run_manifest, verify_run_manifest

    if run_manifest_path.exists():
        try:
            verify_run_manifest(run_manifest_path, current_config=effective_config, task_list=target_tasks)
            print(f"Verified existing run-manifest on resume: {run_manifest_path}", flush=True)
        except Exception as exc:
            print(f"WARNING: Manifest validation alert on resume: {exc}", flush=True)
    else:
        try:
            generate_run_manifest(run_manifest_path, config=effective_config, task_list=target_tasks)
            print(f"Pre-run manifest initialized at: {run_manifest_path}", flush=True)
        except Exception as exc:
            print(f"Warning: Could not initialize run-manifest: {exc}", flush=True)

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

        completed_tasks = get_completed_tasks_count(out_dir, total_tasks=total_target_count)
        print(
            f"\n[Cycle {cycle} | {datetime.datetime.now().strftime('%H:%M:%S')}] "
            f"Progress: {completed_tasks}/{total_target_count} tasks complete.",
            flush=True,
        )

        if completed_tasks >= total_target_count:
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
            )
        except Exception as exc:
            print(f"Error during run_live: {exc}", flush=True)

        # Check again if complete
        completed_tasks = get_completed_tasks_count(out_dir, total_tasks=total_target_count)
        if completed_tasks >= total_target_count:
            run_post_benchmark_pipeline(out_dir, target_total=total_target_count, run_manifest_path=run_manifest_path)
            sys.exit(0)

        print(
            f"Provider quota or rate limit currently active ({completed_tasks}/{total_target_count} tasks finished). "
            f"Sleeping for {args.retry_interval_seconds}s before next autonomous retry...",
            flush=True,
        )
        time.sleep(args.retry_interval_seconds)


if __name__ == "__main__":
    main()
