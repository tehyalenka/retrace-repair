"""Summarize paired public vs heldout success; descriptive only."""
import argparse
import json
from pathlib import Path


def summarize(report):
    rows = report.get("rows", [])
    arms = ("resample", "feedback", "counterfactual")
    summary = {}
    for arm in arms:
        items = [r for r in rows if r.get("condition") == arm]
        summary[arm] = {
            "trials": len(items),
            "public_pass": sum(bool(r.get("success")) for r in items),
            "heldout_pass": sum(bool((r.get("heldout") or {}).get("passed")) for r in items),
            "public_pass_heldout_fail": sum(bool(r.get("success")) and not bool((r.get("heldout") or {}).get("passed")) for r in items),
            "live_calls": sum(r.get("live_calls", 0) for r in items),
        }
    paired = {}
    by_rep = {}
    for row in rows:
        by_rep.setdefault(row.get("repetition"), {})[row.get("condition")] = row
    for arm in ("resample", "feedback"):
        common = [(x["counterfactual"], x[arm]) for x in by_rep.values() if "counterfactual" in x and arm in x]
        paired["counterfactual_vs_" + arm] = {
            "pairs": len(common),
            "counterfactual_only_heldout_pass": sum(bool((a.get("heldout") or {}).get("passed")) and not bool((b.get("heldout") or {}).get("passed")) for a, b in common),
            "baseline_only_heldout_pass": sum(bool((b.get("heldout") or {}).get("passed")) and not bool((a.get("heldout") or {}).get("passed")) for a, b in common),
        }
    return {"arms": summary, "paired": paired,
            "warning": "Descriptive only; repeated trials of one task are not independent benchmark tasks."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    report = json.loads(Path(args.input).read_text(encoding="utf-8"))
    if any("heldout" not in r for r in report.get("rows", [])):
        raise ValueError("Report contains rows without heldout results")
    result = summarize(report)
    print(json.dumps(result, indent=2))
    if args.output:
        Path(args.output).write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
