"""Offline retrieval A/B benchmark with ground-truth file relevance.

Run: python3 benchmarks/v15/evaluate.py --max-files 2 --output benchmark-v15.json
No provider access, network, or additional dependencies are required.
"""
import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from codepilot.repository_analyzer import index_repository, rank_context_files

# Labels are defined independently of either retrieval algorithm.
# Task words deliberately match an entry-point but not its imported dependency.
SCENARIOS = (
    {"name": "checkout_consistency", "entry": "checkout.py", "dependency": "ledger.py",
     "task": "Fix checkout to prevent duplicate charges while keeping the existing API."},
    {"name": "booking_cancellation", "entry": "reservations.py", "dependency": "capacity.py",
     "task": "Fix reservations to prevent repeated cancellation while preserving behavior."},
    {"name": "inventory_commit", "entry": "orders.py", "dependency": "stock.py",
     "task": "Fix orders so failed purchases never commit partial updates."},
    {"name": "report_normalization", "entry": "reports.py", "dependency": "normalizer.py",
     "task": "Refactor reports to handle Unicode consistently without changing its API."},
)


def make_fixture(directory, scenario, distractors=12):
    """Generate a deterministic import-linked repository with unrelated modules."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    entry = scenario["entry"]
    dependency = scenario["dependency"]
    module = Path(dependency).stem
    (directory / entry).write_text(
        "import {}\n\ndef execute(value):\n    return {}.transform(value)\n".format(module, module),
        encoding="utf-8")
    (directory / dependency).write_text(
        "def transform(value):\n    return value\n", encoding="utf-8")
    for index in range(distractors):
        (directory / "a_noise_{:02d}.py".format(index)).write_text(
            "def unrelated_{:02d}(value):\n    return value\n".format(index), encoding="utf-8")
    return {entry, dependency}


def metrics(selected, gold):
    selected, gold = set(selected), set(gold)
    overlap = len(selected & gold)
    return {"precision": overlap / len(selected) if selected else 0.0,
            "recall": overlap / len(gold) if gold else 0.0,
            "f1": 2 * overlap / (len(selected) + len(gold)) if selected or gold else 0.0,
            "relevant_found": overlap}


def evaluate(max_files=2, distractors=12, output=None):
    if max_files < 1 or distractors < 1:
        raise ValueError("max_files and distractors must be positive")
    rows = []
    with tempfile.TemporaryDirectory(prefix="codepilot-v15-") as temp:
        for scenario in SCENARIOS:
            fixture = Path(temp) / scenario["name"]
            gold = make_fixture(fixture, scenario, distractors)
            entries = index_repository(fixture)
            for strategy in ("lexical", "dependency"):
                selected = rank_context_files(entries, scenario["task"], strategy)[:max_files]
                rows.append({"case": scenario["name"], "strategy": strategy,
                             "task": scenario["task"], "repository_files": len(entries),
                             "selected_files": selected, "relevant_files": sorted(gold),
                             **metrics(selected, gold)})
    summary = {}
    for strategy in ("lexical", "dependency"):
        subset = [row for row in rows if row["strategy"] == strategy]
        summary[strategy] = {key: round(sum(row[key] for row in subset) / len(subset), 4)
                             for key in ("precision", "recall", "f1")}
        summary[strategy]["cases"] = len(subset)
    report = {"configuration": {"max_files": max_files, "distractors": distractors,
                                 "offline": True, "gold_labels_predefined": True},
              "summary": summary, "results": rows,
              "limitations": ["Synthetic repositories with direct imports",
                              "Gold labels identify task-relevant files, not a unique edit set",
                              "Retrieval quality does not establish code-editing success",
                              "Import-based retrieval cannot resolve every dynamic or relative import"]}
    if output:
        destination = Path(output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-files", type=int, default=2)
    parser.add_argument("--distractors", type=int, default=12)
    parser.add_argument("--output", default="benchmark-v15-retrieval.json")
    args = parser.parse_args()
    try:
        report = evaluate(args.max_files, args.distractors, args.output)
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(report["summary"], indent=2))
    print("Saved", args.output)


if __name__ == "__main__":
    main()
