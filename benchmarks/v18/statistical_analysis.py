"""Statistical analysis and confidence interval evaluation for RETRACE benchmarks.

Computes:
1. Paired McNemar exact tests between repair strategies.
2. Bootstrap 95% confidence intervals for pass rates and token counts.
3. Cost-normalized metrics: tokens and requests per held-out success.
"""
import argparse
import json
import math
import random
from pathlib import Path
from typing import Dict, List, Tuple


def bootstrap_ci(values: List[float], num_samples: int = 2000, alpha: float = 0.05) -> Tuple[float, float, float]:
    """Calculate mean and non-parametric bootstrap confidence interval."""
    if not values:
        return 0.0, 0.0, 0.0
    mean_val = sum(values) / len(values)
    if len(values) == 1:
        return mean_val, mean_val, mean_val
    n = len(values)
    boot_means = []
    rng = random.Random(42)
    for _ in range(num_samples):
        sample = [rng.choice(values) for _ in range(n)]
        boot_means.append(sum(sample) / n)
    boot_means.sort()
    low_idx = int(math.floor(alpha / 2.0 * num_samples))
    high_idx = int(math.ceil((1.0 - alpha / 2.0) * num_samples)) - 1
    return round(mean_val, 2), round(boot_means[low_idx], 2), round(boot_means[high_idx], 2)


def mcnemar_exact_p_value(b: int, c: int) -> float:
    """Calculate exact two-tailed McNemar test p-value for paired binary outcomes."""
    n = b + c
    if n == 0:
        return 1.0
    # Two-sided exact binomial test with p = 0.5
    min_val = min(b, c)
    prob = sum(math.comb(n, k) * (0.5 ** n) for k in range(min_val + 1))
    return min(1.0, 2.0 * prob)


def analyze_directory(results_dir: str) -> Dict:
    path = Path(results_dir)
    live_files = sorted(path.glob("*-live.json"))
    if not live_files:
        raise ValueError(f"No live benchmark JSON files found in {results_dir}")

    arms_data = {
        "resample": {"tasks": 0, "public_pass": [], "heldout_pass": [], "tokens": [], "live_calls": []},
        "feedback": {"tasks": 0, "public_pass": [], "heldout_pass": [], "tokens": [], "live_calls": []},
        "counterfactual": {"tasks": 0, "public_pass": [], "heldout_pass": [], "tokens": [], "live_calls": []},
    }

    per_task_paired = []

    for file_path in live_files:
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        task_id = file_path.stem.replace("-live", "")
        task_row = {"task": task_id, "arms": {}}

        for row in data.get("rows", []):
            cond = row.get("condition")
            if cond not in arms_data:
                continue
            pub = 1.0 if row.get("success") else 0.0
            held = 1.0 if row.get("heldout", {}).get("passed") else 0.0
            live_calls = row.get("live_calls", 0)
            token_count = row.get("total_tokens", 0)
            # Fallback estimation if token count not directly recorded per row
            if not token_count and "calls" in row:
                token_count = sum(len(c.get("response", "").split()) * 2 for c in row["calls"] if c.get("origin") == "live")

            arms_data[cond]["tasks"] += 1
            arms_data[cond]["public_pass"].append(pub)
            arms_data[cond]["heldout_pass"].append(held)
            arms_data[cond]["tokens"].append(token_count)
            arms_data[cond]["live_calls"].append(live_calls)

            task_row["arms"][cond] = {"public_pass": bool(pub), "heldout_pass": bool(held), "tokens": token_count}

        per_task_paired.append(task_row)

    summary_stats = {}
    for arm, metrics in arms_data.items():
        n = metrics["tasks"]
        if n == 0:
            continue
        pub_mean, pub_low, pub_high = bootstrap_ci(metrics["public_pass"])
        held_mean, held_low, held_high = bootstrap_ci(metrics["heldout_pass"])
        tok_mean, tok_low, tok_high = bootstrap_ci(metrics["tokens"])
        total_tokens = sum(metrics["tokens"])
        held_successes = sum(metrics["heldout_pass"])
        cost_per_success = round(total_tokens / held_successes, 1) if held_successes else None

        summary_stats[arm] = {
            "tasks_evaluated": n,
            "public_pass_rate": round(pub_mean, 4),
            "public_pass_95ci": [pub_low, pub_high],
            "heldout_pass_rate": round(held_mean, 4),
            "heldout_pass_95ci": [held_low, held_high],
            "mean_tokens_per_task": tok_mean,
            "tokens_95ci": [tok_low, tok_high],
            "total_tokens": total_tokens,
            "tokens_per_heldout_success": cost_per_success,
            "total_live_calls": sum(metrics["live_calls"]),
        }

    # McNemar tests between conditions
    mcnemar_results = {}
    pairs = [("resample", "feedback"), ("feedback", "counterfactual"), ("resample", "counterfactual")]
    for a1, a2 in pairs:
        b = 0  # a1 passed heldout, a2 failed
        c = 0  # a1 failed heldout, a2 passed
        for t in per_task_paired:
            arm_a = t["arms"].get(a1, {})
            arm_b = t["arms"].get(a2, {})
            pass_a = arm_a.get("heldout_pass", False)
            pass_b = arm_b.get("heldout_pass", False)
            if pass_a and not pass_b:
                b += 1
            elif not pass_a and pass_b:
                c += 1
        p_val = mcnemar_exact_p_value(b, c)
        mcnemar_results[f"{a1}_vs_{a2}"] = {
            f"{a1}_only_pass": b,
            f"{a2}_only_pass": c,
            "exact_p_value": round(p_val, 4),
            "significant_at_05": p_val < 0.05,
        }

    return {
        "analysis_schema": 1,
        "results_directory": str(path),
        "total_tasks": len(per_task_paired),
        "summary_statistics": summary_stats,
        "mcnemar_paired_tests": mcnemar_results,
        "methodology_notes": [
            "Bootstrap confidence intervals calculated over 2,000 resamples at alpha=0.05",
            "McNemar test evaluates paired heldout pass/fail divergence per task",
            "Cost per success normalizes total tokens by verified held-out repairs",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", default="research-full-suite-22", help="Directory containing live JSON results")
    parser.add_argument("--output", default="statistical-analysis-report.json", help="Output path for JSON report")
    args = parser.parse_args()

    report = analyze_directory(args.results_dir)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
