
"""CodePilot-X v0.3: task-specific benchmark evaluation."""

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from codepilot.agent import run_agent


TASKS = [
    {
        "id": "auth_casefold",
        "file": "auth.py",
        "initial": (
            'def authenticate(username, password):\n'
            '    return username == "admin" and password == "secret"\n'
        ),
        "task": (
            "Make username matching case-insensitive while "
            "keeping passwords case-sensitive."
        ),
        "checks": [
            'assert authenticate("ADMIN", "secret") is True',
            'assert authenticate("AdMiN", "secret") is True',
            'assert authenticate("ADMIN", "SECRET") is False',
            'assert authenticate("guest", "secret") is False',
        ],
    },
    {
        "id": "safe_division",
        "file": "math_utils.py",
        "initial": (
            "def safe_divide(a, b):\n"
            "    return a / b\n"
        ),
        "task": (
            "Change safe_divide so division by zero returns None. "
            "Preserve normal division behavior."
        ),
        "checks": [
            "assert safe_divide(8, 2) == 4",
            "assert safe_divide(5, 2) == 2.5",
            "assert safe_divide(8, 0) is None",
            "assert safe_divide(-8, 2) == -4",
        ],
    },
    {
        "id": "stable_unique",
        "file": "collections_utils.py",
        "initial": (
            "def unique_items(items):\n"
            "    return list(set(items))\n"
        ),
        "task": (
            "Remove duplicates while preserving first-occurrence "
            "order. Support lists of integers and strings."
        ),
        "checks": [
            "assert unique_items([3, 1, 3, 2, 1]) == [3, 1, 2]",
            'assert unique_items(["b", "a", "b"]) == ["b", "a"]',
            "assert unique_items([]) == []",
        ],
    },
]


def verify_generated_code(task, generated):
    """Evaluate generated code against withheld checks."""
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)

        (root / task["file"]).write_text(
            generated, encoding="utf-8"
        )

        module_name = Path(task["file"]).stem

        test_source = (
            "from {} import *\n".format(module_name)
            + "\n".join(task["checks"])
            + "\n"
        )

        test_file = root / "hidden_checks.py"
        test_file.write_text(test_source, encoding="utf-8")

        try:
            result = subprocess.run(
                [sys.executable, str(test_file)],
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=15,
            )

            return (
                result.returncode == 0,
                (result.stdout + result.stderr)[-3000:],
            )

        except subprocess.TimeoutExpired:
            return False, "Hidden checks timed out"


def evaluate(attempts):
    results = []

    for task in TASKS:
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)

            (repo / task["file"]).write_text(
                task["initial"], encoding="utf-8"
            )

            tests = repo / "tests"
            tests.mkdir()

            # The agent sees a basic smoke test.
            # Task-specific checks are withheld.
            (tests / "test_smoke.py").write_text(
                "import unittest\n"
                "class Smoke(unittest.TestCase):\n"
                "    def test_smoke(self):\n"
                "        self.assertTrue(True)\n",
                encoding="utf-8",
            )

            start = time.monotonic()

            record = {
                "id": task["id"],
                "task": task["task"],
            }

            try:
                response = run_agent(
                    str(repo),
                    task["task"],
                    attempts=attempts,
                )

                record["existing_tests_passed"] = bool(
                    response["success"]
                )

                record["attempts"] = len(
                    response["history"]
                )

                generated = response.get(
                    "files", {}
                ).get(task["file"])

                if generated is None:
                    passed = False
                    output = "Agent did not return the target file"
                else:
                    passed, output = verify_generated_code(
                        task, generated
                    )

                record["hidden_tests_passed"] = passed
                record["hidden_test_output"] = output

            except Exception as exc:
                record["existing_tests_passed"] = False
                record["hidden_tests_passed"] = False
                record["error"] = str(exc)[:1000]

            record["elapsed_seconds"] = round(
                time.monotonic() - start, 2
            )

            results.append(record)

            print(
                "{}: existing={} hidden={}".format(
                    task["id"],
                    record["existing_tests_passed"],
                    record["hidden_tests_passed"],
                ),
                flush=True,
            )

    count = len(results)

    return {
        "benchmark": "CodePilot-X v0.3 pilot",
        "task_count": count,
        "existing_test_pass_rate": sum(
            r["existing_tests_passed"] for r in results
        ) / count,
        "hidden_test_task_success_rate": sum(
            r["hidden_tests_passed"] for r in results
        ) / count,
        "results": results,
        "limitations": (
            "Three small synthetic tasks. Not SWE-bench. "
            "Tests execute generated Python code."
        ),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--attempts",
        type=int,
        default=2,
        choices=range(1, 6),
    )

    parser.add_argument(
        "--output",
        default="benchmark-v03.json",
    )

    args = parser.parse_args()

    report = evaluate(args.attempts)

    Path(args.output).write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    print(
        "Saved {} | Hidden-test success: {:.0%}".format(
            args.output,
            report["hidden_test_task_success_rate"],
        )
    )
