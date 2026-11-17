"""Statistical analysis and confidence interval evaluation for RETRACE benchmarks.

Computes:
1. Paired McNemar exact tests between repair strategies on strictly paired tasks.
2. Bootstrap 95% confidence intervals for pass rates and provider token counts.
3. Cost-normalized metrics: provider tokens and requests per held-out success.
4. Separate accounting of provider-reported vs. estimated tokens with strict input validation.
"""
import argparse
import json
import math
import random
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def bootstrap_ci(values: List[float], num_samples: int = 2000, alpha: float = 0.05) -> Tuple[float, float, float]:
    """Calculate mean and non-parametric bootstrap confidence interval."""
    if not values:
        return 0.0, 0.0, 0.0
    mean_val = sum(values) / len(values)
    if len(values) == 1:
        return round(mean_val, 2), round(mean_val, 2), round(mean_val, 2)
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
        "resample": {
            "tasks": 0,
            "public_pass": [],
            "heldout_pass": [],
            "provider_tokens": [],
            "estimated_tokens": [],
            "live_calls": [],
        },
        "feedback": {
            "tasks": 0,
            "public_pass": [],
            "heldout_pass": [],
            "provider_tokens": [],
            "estimated_tokens": [],
            "live_calls": [],
        },
        "counterfactual": {
            "tasks": 0,
            "public_pass": [],
            "heldout_pass": [],
            "provider_tokens": [],
            "estimated_tokens": [],
            "live_calls": [],
        },
    }

    per_task_paired = []
    seen_tasks = set()

    for file_path in live_files:
        try:
            content = file_path.read_text(encoding="utf-8")
            data = json.loads(content)
        except Exception as exc:
            raise ValueError(f"Malformed benchmark JSON file: {file_path} ({exc})") from exc

        task_id = file_path.stem.replace("-live", "")
        if task_id in seen_tasks:
            raise ValueError(f"Duplicate task JSON file encountered: {task_id}")
        seen_tasks.add(task_id)

        task_row = {"task": task_id, "arms": {}}
        seen_conditions = set()

        for row in data.get("rows", []):
            cond = row.get("condition")
            if cond not in arms_data:
                continue
            if cond in seen_conditions:
                raise ValueError(f"Duplicate strategy row '{cond}' in task '{task_id}'")
            seen_conditions.add(cond)

            pub = 1.0 if row.get("success") else 0.0
            held = 1.0 if row.get("heldout", {}).get("passed") else 0.0
            live_calls = int(row.get("live_calls", 0))

            # Extract provider-reported tokens from request_accounting
            req_acc = row.get("request_accounting") or {}
            prompt_tok = req_acc.get("prompt_tokens")
            comp_tok = req_acc.get("completion_tokens")

            provider_tok: Optional[int] = None
            estimated_tok: Optional[int] = None

            if prompt_tok is not None and comp_tok is not None:
                provider_tok = int(prompt_tok) + int(comp_tok)
            elif "calls" in row:
                # Disaggregate estimation: explicitly marked as estimated, never conflated with provider-reported
                estimated_tok = sum(
                    len(c.get("response", "").split()) * 2
                    for c in row["calls"]
                    if c.get("origin") == "live"
                )

            arms_data[cond]["tasks"] += 1
            arms_data[cond]["public_pass"].append(pub)
            arms_data[cond]["heldout_pass"].append(held)
            arms_data[cond]["live_calls"].append(live_calls)

            if provider_tok is not None:
                arms_data[cond]["provider_tokens"].append(provider_tok)
            if estimated_tok is not None:
                arms_data[cond]["estimated_tokens"].append(estimated_tok)

            task_row["arms"][cond] = {
                "public_pass": bool(pub),
                "heldout_pass": bool(held),
                "provider_tokens": provider_tok,
                "estimated_tokens": estimated_tok,
                "live_calls": live_calls,
            }

        per_task_paired.append(task_row)

    summary_stats = {}
    for arm, metrics in arms_data.items():
        n = metrics["tasks"]
        if n == 0:
            continue
        pub_mean, pub_low, pub_high = bootstrap_ci(metrics["public_pass"])
        held_mean, held_low, held_high = bootstrap_ci(metrics["heldout_pass"])

        has_provider = len(metrics["provider_tokens"]) > 0
        tok_values = [float(v) for v in metrics["provider_tokens"]] if has_provider else [float(v) for v in metrics["estimated_tokens"]]
        tok_mean, tok_low, tok_high = bootstrap_ci(tok_values) if tok_values else (0.0, 0.0, 0.0)

        total_provider_tokens = sum(metrics["provider_tokens"]) if has_provider else None
        total_estimated_tokens = sum(metrics["estimated_tokens"]) if metrics["estimated_tokens"] else None
        held_successes = sum(metrics["heldout_pass"])
        cost_per_success = round(total_provider_tokens / held_successes, 1) if (total_provider_tokens and held_successes) else None

        summary_stats[arm] = {
            "tasks_evaluated": n,
            "public_pass_rate": round(pub_mean, 4),
            "public_pass_95ci": [pub_low, pub_high],
            "heldout_pass_rate": round(held_mean, 4),
            "heldout_pass_95ci": [held_low, held_high],
            "mean_tokens_per_task": tok_mean,
            "tokens_95ci": [tok_low, tok_high],
            "provider_reported_tokens": total_provider_tokens,
            "estimated_tokens": total_estimated_tokens,
            "token_accounting_mode": "provider_verified" if has_provider else "estimated_heuristic",
            "tokens_per_heldout_success": cost_per_success,
            "total_live_calls": sum(metrics["live_calls"]),
        }

    # Strict McNemar tests: only include tasks where BOTH strategies have valid observations
    mcnemar_results = {}
    pairs = [("resample", "feedback"), ("feedback", "counterfactual"), ("resample", "counterfactual")]
    for a1, a2 in pairs:
        b = 0  # a1 passed heldout, a2 failed
        c = 0  # a1 failed heldout, a2 passed
        paired_evaluable = 0
        dropped_tasks = []

        for t in per_task_paired:
            has_a1 = a1 in t["arms"]
            has_a2 = a2 in t["arms"]
            if not has_a1 or not has_a2:
                dropped_tasks.append(t["task"])
                continue

            paired_evaluable += 1
            pass_a = t["arms"][a1]["heldout_pass"]
            pass_b = t["arms"][a2]["heldout_pass"]
            if pass_a and not pass_b:
                b += 1
            elif not pass_a and pass_b:
                c += 1

        p_val = mcnemar_exact_p_value(b, c)
        mcnemar_results[f"{a1}_vs_{a2}"] = {
            "paired_evaluable_tasks": paired_evaluable,
            "dropped_missing_strategy_tasks": dropped_tasks,
            f"{a1}_only_pass": b,
            f"{a2}_only_pass": c,
            "both_pass_or_both_fail": paired_evaluable - (b + c),
            "exact_p_value": round(p_val, 4),
            "significant_at_05": p_val < 0.05,
            "conclusion": (
                "Statistically significant divergence"
                if p_val < 0.05
                else "No statistically significant divergence observed (inconclusive / identical held-out outcomes)"
            ),
        }

    return {
        "analysis_schema": 2,
        "results_directory": str(path),
        "total_tasks": len(per_task_paired),
        "summary_statistics": summary_stats,
        "mcnemar_paired_tests": mcnemar_results,
        "methodology_notes": [
            "Strict paired evaluation: tasks missing either arm are excluded from McNemar comparison rather than imputed as failures.",
            "Provider-reported tokens extracted directly from request_accounting without heuristic substitution.",
            "Bootstrap confidence intervals calculated over 2,000 resamples at alpha=0.05.",
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
