"""Execute candidate repairs against independent repository snapshots.

This module is not a security sandbox. Only replay trusted code.
"""

import ast
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


def score_candidate_defense(edits):
    """Compute a defensive structural quality score for candidate edits.

    Rewards:
    - Explicit parameter validation guards (isinstance, raise ValueError, raise TypeError).
    - Transactional rollback / exception re-raise (except ...: rollback(); raise).
    - Clean boundary checks (if statements).

    Penalties:
    - Swallowed exceptions (except ...: pass).
    - Empty returns on exceptions without logging or re-raise.
    - Gratuitous code bloat (Occam's AST penalty).
    """
    if not edits or not isinstance(edits, list):
        return 0.0

    score = 0.0
    for edit in edits:
        if not isinstance(edit, dict):
            continue
        content = edit.get("content")
        if not content or not isinstance(content, str):
            continue
        try:
            tree = ast.parse(content)
        except Exception:
            score -= 100.0
            continue

        node_count = 0
        for node in ast.walk(tree):
            node_count += 1
            # 1. Detect swallowed exceptions (severe penalty for specification gaming)
            if isinstance(node, ast.ExceptHandler):
                if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                    score -= 50.0
                elif len(node.body) == 1 and isinstance(node.body[0], ast.Return) and node.body[0].value is None:
                    score -= 30.0

            # 2. Reward explicit exception raising (parameter validation or re-raising)
            if isinstance(node, ast.Raise):
                score += 15.0

            # 3. Reward explicit condition checks (guards, isinstance)
            if isinstance(node, ast.If):
                score += 5.0

            # 4. Reward try/finally or rollback cleanup
            if isinstance(node, ast.Try) and node.finalbody:
                score += 15.0

        # Occam penalty for bloated AST churn
        score -= round(node_count * 0.02, 2)

    return round(score, 2)


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
    """Select a public-test-passing candidate using defensive AST scoring.

    Public-test passing candidates are ranked by their defensive structural quality score.
    Ties are resolved by input order. Held-out tests are never used.
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

    selected = None
    scores = {}
    if passing:
        for idx in passing:
            res = results[idx]
            edits = res.get("edits")
            scores[idx] = score_candidate_defense(edits) if edits else 0.0
        # Sort passing candidates by defensive score descending, then candidate index ascending
        sorted_passing = sorted(passing, key=lambda i: (scores[i], -i), reverse=True)
        selected = sorted_passing[0]

    return {
        "selected_index": selected,
        "passing_indices": passing,
        "candidates_evaluated": len(results),
        "defensive_scores": scores,
        "selection_reason": (
            "highest_defensive_scoring_public_passing_candidate"
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
            "edits": edits,
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
