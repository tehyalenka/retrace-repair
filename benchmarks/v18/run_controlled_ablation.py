"""Execute Controlled Candidate-Selection Ablation across the 6 Frozen State Machines.

Methodological Guarantees:
1. Candidate Pool Caching: Standard prompt (P_std) and Invariant prompt (P_inv)
   are generated once with k=2 candidates per task under matched temperature (T=0.7).
2. Immutable Reused Pools:
   - Config 1 (Baseline) & Config 3 (AST-Only) reuse exact identical pool P_std.
   - Config 2 (Prompt-Only) & Config 4 (Combined) reuse exact identical pool P_inv.
   - Zero generation variance when isolating selector heuristics.
3. Independent, Access-Controlled Held-Out Evaluation:
   - Public smoke tests determine candidate eligibility V(Ci).
   - Held-out invariant audit H(Ci) runs offline without leaking to prompts or policy.
4. Telemetry with Orthogonal Causal Dimensions:
   - selection_eligibility: ELIGIBLE_CANDIDATES_AVAILABLE vs NO_ELIGIBLE_CANDIDATES
   - pool_heldout_correctness: CORRECT_ELIGIBLE_EXISTS vs CORRECT_INELIGIBLE_ONLY vs NO_CORRECT_IN_POOL
   - Derived verdict: SUCCESSFUL_SELECTION, SELECTION_FAILURE, NO_ELIGIBLE_CANDIDATE, NO_VALID_CANDIDATE
"""

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from benchmarks.v18 import task_suite_runner
from benchmarks.v18.candidate_selection_ablation import (
    CandidatePool,
    NO_ELIGIBLE_CANDIDATE,
    NO_VALID_CANDIDATE,
    SELECTION_FAILURE,
    SUCCESSFUL_SELECTION,
    diagnose_selection,
    evaluate_ablation_on_pool,
    select_ast_ranked,
    select_greedy,
)
from codepilot.agent import (
    SYSTEM,
    repository_map,
    retrieve_context,
)
from codepilot.counterfactual_replay import replay_candidate
from codepilot.replay_generation import generate_replay_candidates


DEFAULT_TASKS = [
    "enterprise_circuit_breaker",
    "enterprise_saga_coordinator",
    "enterprise_dead_letter_retry",
    "enterprise_cache_stampede_mutex",
    "enterprise_bulkhead_isolation",
    "enterprise_outbox_publisher",
]


def create_task_messages(repo_path: Path, task_description: str) -> List[Dict[str, str]]:
    """Build conversation context identical to agent runner initialization."""
    repo_map = repository_map(repo_path)
    context = retrieve_context(repo_path, task_description, max_files=6, strategy="lexical")
    return [
        {"role": "system", "content": SYSTEM},
        {
            "role": "user",
            "content": (
                f"Task: {task_description}\n\n"
                f"Repository map:\n{repo_map}\n\n"
                f"Selected source context:\n{context}"
            ),
        },
    ]


def run_candidate_ablation_for_task(
    task_id: str,
    output_dir: Path,
    candidate_count: int = 2,
    temperature: float = 0.7,
    use_cache: bool = True,
) -> Dict[str, Any]:
    """Execute ablation for a single task across both prompt arms and selectors."""
    suite_tasks = {t["id"]: t for t in task_suite_runner.tasks()}
    if task_id not in suite_tasks:
        raise ValueError(f"Unknown task: {task_id}")

    task_def = suite_tasks[task_id]
    repo_path = task_suite_runner.ROOT / task_def["repo"]
    public_verifier = (task_suite_runner.ROOT / task_def["public_verifier"]).read_text(encoding="utf-8")
    heldout_verifier = (task_suite_runner.ROOT / task_def["heldout_verifier"]).read_text(encoding="utf-8")

    pools_dir = output_dir / "pools"
    pools_dir.mkdir(parents=True, exist_ok=True)

    pool_telemetry = {}

    for condition in ["standard", "invariant"]:
        pool_file = pools_dir / f"{task_id}_{condition}.json"

        if use_cache and pool_file.exists():
            pool = CandidatePool.load(pool_file)
        else:
            messages = create_task_messages(repo_path, task_def["task"])
            generation = generate_replay_candidates(
                messages=messages,
                candidate_count=candidate_count,
                temperature=temperature,
                prompt_condition=condition,
            )

            pool = CandidatePool(task_id=task_id, prompt_condition=condition)

            # Evaluate each candidate against public verification (eligibility)
            # and independent, access-controlled held-out audit
            for idx, cand_edits in enumerate(generation["candidates"]):
                rec = generation["generation_records"][idx] if idx < len(generation["generation_records"]) else {}
                summary = rec.get("reasoning_summary", "")

                # 1. Public verification gate
                pub_res = replay_candidate(repo_path, cand_edits, public_verifier=public_verifier)

                # 2. Independent access-controlled held-out audit
                held_res = replay_candidate(repo_path, cand_edits, public_verifier=heldout_verifier)

                pool.add_candidate(
                    candidate_index=idx,
                    edits=cand_edits,
                    reasoning_summary=summary,
                    public_result=pub_res,
                    heldout_result=held_res,
                )

            # Freeze pool to disk
            pool.save(pool_file)

        # Evaluate both selectors over the identical pool
        telem = evaluate_ablation_on_pool(pool)
        pool_telemetry[condition] = telem

    std_telem = pool_telemetry["standard"]
    inv_telem = pool_telemetry["invariant"]

    # Map to the 4 factorial configurations
    return {
        "task_id": task_id,
        "standard_pool": std_telem,
        "invariant_pool": inv_telem,
        "configs": {
            "config1_baseline": std_telem["selectors"]["greedy"],
            "config3_ast_only": std_telem["selectors"]["ast_ranked"],
            "config2_prompt_only": inv_telem["selectors"]["greedy"],
            "config4_combined": inv_telem["selectors"]["ast_ranked"],
        },
        "standard_disagreed": std_telem["policy_diverged"],
        "standard_outcome_differed": std_telem["outcome_diverged"],
        "invariant_disagreed": inv_telem["policy_diverged"],
        "invariant_outcome_differed": inv_telem["outcome_diverged"],
    }


def run_ablation_suite(
    tasks: List[str],
    output_dir: Path,
    candidate_count: int = 2,
    temperature: float = 0.7,
    use_cache: bool = True,
) -> List[Dict[str, Any]]:
    """Execute full ablation suite over target tasks and emit structured artifacts."""
    output_dir.mkdir(parents=True, exist_ok=True)
    telemetry_file = output_dir / "ablation-telemetry.jsonl"
    summary_csv = output_dir / "ablation-summary.csv"

    results = []
    with open(telemetry_file, "a", encoding="utf-8") as telem_f:
        for task_id in tasks:
            print(f"[{time.strftime('%H:%M:%S')}] Evaluating task: {task_id}...")
            res = run_candidate_ablation_for_task(
                task_id=task_id,
                output_dir=output_dir,
                candidate_count=candidate_count,
                temperature=temperature,
                use_cache=use_cache,
            )
            results.append(res)
            telem_f.write(json.dumps(res) + "\n")
            telem_f.flush()

    # Emit Summary CSV
    with open(summary_csv, "w", newline="", encoding="utf-8") as csv_f:
        writer = csv.writer(csv_f)
        writer.writerow([
            "task_id",
            "config1_baseline_heldout",
            "config1_baseline_diagnosis",
            "config3_ast_only_heldout",
            "config3_ast_only_diagnosis",
            "config2_prompt_only_heldout",
            "config2_prompt_only_diagnosis",
            "config4_combined_heldout",
            "config4_combined_diagnosis",
            "std_selector_disagreed",
            "inv_selector_disagreed",
        ])
        for r in results:
            cfg = r["configs"]
            writer.writerow([
                r["task_id"],
                cfg["config1_baseline"]["heldout_passed"],
                cfg["config1_baseline"]["diagnosis"],
                cfg["config3_ast_only"]["heldout_passed"],
                cfg["config3_ast_only"]["diagnosis"],
                cfg["config2_prompt_only"]["heldout_passed"],
                cfg["config2_prompt_only"]["diagnosis"],
                cfg["config4_combined"]["heldout_passed"],
                cfg["config4_combined"]["diagnosis"],
                r["standard_disagreed"],
                r["invariant_disagreed"],
            ])

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run RETRACE Controlled Candidate-Selection Ablation")
    parser.add_argument("--output-dir", type=str, default="research-controlled-ablation")
    parser.add_argument("--tasks", type=str, default=",".join(DEFAULT_TASKS))
    parser.add_argument("--candidates", type=int, default=2)
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--no-cache", action="store_true")
    args = parser.parse_args()

    task_list = [t.strip() for t in args.tasks.split(",") if t.strip()]
    out = Path(args.output_dir)

    print("======================================================================")
    print("RETRACE CONTROLLED CANDIDATE-SELECTION ABLATION RUNNER")
    print(f"Target Tasks: {len(task_list)} tasks")
    print(f"Output Directory: {out}")
    print(f"Candidates per Pool: {args.candidates} (T={args.temperature})")
    print("======================================================================")

    res = run_ablation_suite(
        tasks=task_list,
        output_dir=out,
        candidate_count=args.candidates,
        temperature=args.temperature,
        use_cache=not args.no_cache,
    )
    print("======================================================================")
    print(f"Ablation run complete! Telemetry saved to {out}/ablation-telemetry.jsonl")
    print("======================================================================")
