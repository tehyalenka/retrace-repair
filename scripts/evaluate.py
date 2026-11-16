"""Run tasks sequentially and save a transparent small-sample evaluation."""
import json
import sys
from pathlib import Path

from codepilot.agent import run_agent


def main():
    tasks = json.loads(Path(sys.argv[1] if len(sys.argv) > 1 else "examples/tasks.json").read_text())
    results = []
    for task in tasks:
        try:
            result = run_agent(task["repository"], task["task"])
            results.append({"id": task["id"], "passed_existing_tests": result["success"], "attempts": len(result["history"])})
        except Exception as exc:
            results.append({"id": task["id"], "passed_existing_tests": False, "error": str(exc)})
    print(json.dumps({"results": results, "existing_test_pass_rate": sum(r["passed_existing_tests"] for r in results) / len(results) if results else None}, indent=2))
    print("NOTE: Existing-test pass rate is NOT proof of task correctness. Add task-specific hidden tests before claiming solve rate.")


if __name__ == "__main__":
    main()
