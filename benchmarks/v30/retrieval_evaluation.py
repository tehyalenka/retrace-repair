"""Offline evaluation of lexical vs dependency-aware retrieval."""

import json
import tempfile
from pathlib import Path

from codepilot.repository_analyzer import (
    index_repository,
    rank_context_files,
)


def make_repository(root, files):
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


def recall_at_k(ranking, relevant, k):
    return len(set(ranking[:k]) & set(relevant)) / len(relevant)


def evaluate_case(case):
    with tempfile.TemporaryDirectory() as temp:
        repo = Path(temp)
        make_repository(repo, case["files"])
        entries = index_repository(repo)

        results = {}
        for strategy in ("lexical", "dependency"):
            ranking = rank_context_files(
                entries,
                case["task"],
                strategy=strategy,
                repo_path=repo,
            )

            results[strategy] = {
                "top_10": ranking[:10],
                "recall_at_3": recall_at_k(
                    ranking, case["relevant"], 3
                ),
                "recall_at_5": recall_at_k(
                    ranking, case["relevant"], 5
                ),
                "recall_at_10": recall_at_k(
                    ranking, case["relevant"], 10
                ),
            }

        return results


def build_cases():
    cases = []

    for index in range(12):
        service = "Service{}".format(index)
        dependency = "Dependency{}".format(index)

        files = {
            "service.py": (
                "class {}:\n"
                "    def __init__(self, dependency: {}):\n"
                "        self.dependency = dependency\n"
            ).format(service, dependency),
            "dependency.py": "class {}:\n    pass\n".format(
                dependency
            ),
        }

        for number in range(12):
            files["aaa_noise_{}.py".format(number)] = (
                "class Noise{}:\n    pass\n".format(number)
            )

        cases.append({
            "name": "case_{}".format(index),
            "task": "Implement {}".format(service),
            "files": files,
            "relevant": ["service.py", "dependency.py"],
        })

    return cases


def main():
    cases = build_cases()
    records = []

    for case in cases:
        result = evaluate_case(case)
        records.append({
            "name": case["name"],
            "results": result,
        })

    summary = {}

    for strategy in ("lexical", "dependency"):
        summary[strategy] = {}

        for k in (3, 5, 10):
            key = "recall_at_{}".format(k)
            values = [
                record["results"][strategy][key]
                for record in records
            ]
            summary[strategy][key] = sum(values) / len(values)

    report = {
        "case_count": len(cases),
        "summary": summary,
        "cases": records,
    }

    output = Path("benchmarks/v30/retrieval_report.json")
    output.write_text(json.dumps(report, indent=2))

    print(json.dumps(summary, indent=2))
    print("\nSaved:", output)


if __name__ == "__main__":
    main()
