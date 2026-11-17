"""Execute candidate repairs against independent repository snapshots.

This module is not a security sandbox. Only replay trusted code.
"""

import shutil
import tempfile
from pathlib import Path

from codepilot.agent import (
    apply_edits,
    discover_python_files,
    run_tests,
)


IGNORED = shutil.ignore_patterns(
    ".git", ".venv", "__pycache__", "node_modules", ".env"
)


def replay_candidate(repo_path, edits, test_timeout=30, public_verifier=None):
    """Apply a candidate to a fresh copy and observe its public-test result.

    The original repository is never modified.
    """
    original = Path(repo_path).expanduser().resolve()

    if not original.is_dir():
        raise ValueError("Repository directory does not exist")

    allowed = set(discover_python_files(original))

    if not allowed:
        raise ValueError("No Python files discovered")

    with tempfile.TemporaryDirectory(prefix="retrace-replay-") as temp:
        workspace = Path(temp) / "repo"
        shutil.copytree(
            original,
            workspace,
            ignore=IGNORED,
            symlinks=False,
        )

        if public_verifier is not None:
            content = None
            try:
                verifier_path = Path(public_verifier).expanduser().resolve()
                if verifier_path.is_file():
                    content = verifier_path.read_bytes()
            except (OSError, ValueError):
                pass
            if content is None:
                if isinstance(public_verifier, str) and public_verifier.strip():
                    content = public_verifier.encode("utf-8")
                else:
                    raise ValueError(
                        "Public verifier must be an existing file path or nonempty unittest source string"
                    )

            tests_dir = workspace / "tests"
            tests_dir.mkdir(exist_ok=True)
            (tests_dir / "test_retrace_public.py").write_bytes(content)

        try:
            changed = apply_edits(workspace, edits, allowed)
        except (ValueError, SyntaxError, KeyError, OSError) as exc:
            return {
                "passed": False,
                "changed_files": [],
                "failure_stage": "edit_validation",
                "output": str(exc),
            }

        result = run_tests(workspace, timeout=test_timeout)

        return {
            "passed": result["passed"],
            "changed_files": changed,
            "failure_stage": None if result["passed"] else "smoke_tests",
            "tests_run": result["tests_run"],
            "output": result["output"],
        }


def compare_candidates(results):
    """Select a public-test-passing candidate, without using held-out tests.

    Ties are resolved by input order, not an unsupported quality claim.
    """
    if not results:
        raise ValueError("At least one candidate result is required")

    for index, result in enumerate(results):
        if not isinstance(result, dict) or not isinstance(result.get("passed"), bool):
            raise ValueError("Each result must contain a boolean 'passed' field")

    passing = [
        index for index, result in enumerate(results)
        if result["passed"]
    ]

    selected = passing[0] if passing else None

    return {
        "selected_index": selected,
        "passing_indices": passing,
        "candidates_evaluated": len(results),
        "selection_reason": (
            "first_public_test_passing_candidate"
            if selected is not None
            else "no_candidate_passed"
        ),
    }


def replay_alternatives(
    repo_path,
    candidates,
    test_timeout=30,
    public_verifier=None,
):
    """Replay candidate edit batches independently and compare outcomes.

    Candidate generation is external to this function.
    Held-out tests are never used for candidate selection.
    """
    if not candidates:
        raise ValueError("At least one candidate is required")

    results = []

    for index, edits in enumerate(candidates):
        result = replay_candidate(
            repo_path,
            edits,
            test_timeout=test_timeout,
            public_verifier=public_verifier,
        )

        results.append({
            "candidate_index": index,
            **result,
        })

    comparison = compare_candidates(results)

    return {
        "results": results,
        "selection": comparison,
        "model_requests": 0,
        "test_executions": sum(
            1 for result in results
            if "tests_run" in result
        ),
    }
