"""Controlled Candidate-Selection Ablation Protocol for RETRACE v2.0.

This module isolates candidate selection heuristics (AST structural ranking)
from candidate generation (prompt framing) by:
1. Generating immutable, cached candidate pools (P_std and P_inv) per task.
2. Exhaustively evaluating all candidates against visible verification tests
   (eligibility) and independent, access-controlled held-out invariant tests.
3. Evaluating both Greedy and AST-Ranked selection policies on the identical candidate pool.
4. Logging structured candidate-level telemetry to distinguish:
   - SUCCESSFUL_SELECTION: The selected candidate satisfies held-out tests.
   - SELECTION_FAILURE: At least one eligible candidate satisfies held-out tests,
     but the policy selected a candidate that fails.
   - NO_VALID_CANDIDATE: No eligible candidate in the pool satisfies held-out tests.
"""

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from codepilot.counterfactual_replay import (
    replay_candidate,
    score_candidate_defense,
)
from codepilot.agent import run_verification


# ---------------------------------------------------------------------------
# Causal Diagnosis Categories
# ---------------------------------------------------------------------------
SUCCESSFUL_SELECTION = "SUCCESSFUL_SELECTION"
SELECTION_FAILURE = "SELECTION_FAILURE"
NO_VALID_CANDIDATE = "NO_VALID_CANDIDATE"


def hash_edits(edits: List[Dict[str, Any]]) -> str:
    """Compute deterministic SHA-256 hash of an edits batch."""
    payload = json.dumps(edits, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


class CandidatePool:
    """Represents a frozen pool of candidate patches for a task and prompt condition."""

    def __init__(self, task_id: str, prompt_condition: str):
        self.task_id = task_id
        self.prompt_condition = prompt_condition  # "standard" or "invariant"
        self.candidates: List[Dict[str, Any]] = []

    def add_candidate(
        self,
        candidate_index: int,
        edits: List[Dict[str, Any]],
        reasoning_summary: str = "",
        public_result: Optional[Dict[str, Any]] = None,
        heldout_result: Optional[Dict[str, Any]] = None,
    ) -> None:
        c_hash = hash_edits(edits)
        ast_score = score_candidate_defense(edits)

        self.candidates.append({
            "candidate_index": candidate_index,
            "hash": c_hash,
            "reasoning_summary": reasoning_summary,
            "edits": edits,
            "ast_score": ast_score,
            "public_passed": bool(public_result.get("passed")) if public_result else False,
            "public_output": (public_result.get("output") or "")[:500] if public_result else "",
            "heldout_passed": bool(heldout_result.get("passed")) if heldout_result else False,
            "heldout_output": (heldout_result.get("output") or "")[:500] if heldout_result else "",
        })

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "prompt_condition": self.prompt_condition,
            "candidate_count": len(self.candidates),
            "candidates": self.candidates,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CandidatePool":
        pool = cls(data["task_id"], data["prompt_condition"])
        pool.candidates = data.get("candidates", [])
        return pool

    def save(self, filepath: Path) -> None:
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, filepath: Path) -> "CandidatePool":
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)


# ---------------------------------------------------------------------------
# Policy Selectors
# ---------------------------------------------------------------------------
def select_greedy(pool: CandidatePool) -> Optional[int]:
    """Select the first eligible candidate (passes visible public tests)."""
    for c in pool.candidates:
        if c.get("public_passed"):
            return c["candidate_index"]
    return None


def select_ast_ranked(pool: CandidatePool) -> Optional[int]:
    """Select highest AST defense-scoring eligible candidate (passes visible tests).

    Ties broken by input order (earlier index first).
    """
    eligible = [c for c in pool.candidates if c.get("public_passed")]
    if not eligible:
        return None

    # Sort by ast_score desc, then candidate_index asc
    sorted_eligible = sorted(
        eligible,
        key=lambda c: (c.get("ast_score", 0.0), -c["candidate_index"]),
        reverse=True,
    )
    return sorted_eligible[0]["candidate_index"]


# ---------------------------------------------------------------------------
# Causal Diagnosis Engine
# ---------------------------------------------------------------------------
def diagnose_selection(pool: CandidatePool, selected_index: Optional[int]) -> Dict[str, Any]:
    """Evaluate candidate selection against held-out ground truth invariants.

    Rules:
    - SUCCESSFUL_SELECTION: The selected candidate satisfies held-out tests.
    - SELECTION_FAILURE: At least one eligible candidate satisfies held-out tests,
      but the selected candidate fails (or no candidate was selected).
    - NO_VALID_CANDIDATE: Neither candidate in the eligible pool satisfies held-out tests.
    """
    eligible = [c for c in pool.candidates if c.get("public_passed")]
    has_valid_eligible = any(c.get("heldout_passed") for c in eligible)

    if selected_index is not None:
        selected_candidate = next(
            (c for c in pool.candidates if c["candidate_index"] == selected_index),
            None,
        )
        if selected_candidate and selected_candidate.get("heldout_passed"):
            return {
                "verdict": SUCCESSFUL_SELECTION,
                "selected_index": selected_index,
                "selected_heldout": True,
                "explanation": "Selected candidate satisfies held-out invariant contract.",
            }

    # If selected candidate failed or None was selected:
    if has_valid_eligible:
        return {
            "verdict": SELECTION_FAILURE,
            "selected_index": selected_index,
            "selected_heldout": False,
            "explanation": (
                "An eligible, invariant-correct candidate existed in the pool, "
                "but the selection policy chose an incorrect alternative or none."
            ),
        }

    return {
        "verdict": NO_VALID_CANDIDATE,
        "selected_index": selected_index,
        "selected_heldout": False,
        "explanation": "No eligible candidate in the pool satisfied held-out tests (generation failure).",
    }


def evaluate_ablation_on_pool(pool: CandidatePool) -> Dict[str, Any]:
    """Run both Greedy and AST selectors on the identical pool and return telemetry."""
    greedy_idx = select_greedy(pool)
    ast_idx = select_ast_ranked(pool)

    greedy_diag = diagnose_selection(pool, greedy_idx)
    ast_diag = diagnose_selection(pool, ast_idx)

    # Check if policy decision diverged on identical candidate pool
    policy_diverged = greedy_idx != ast_idx
    outcome_diverged = greedy_diag["selected_heldout"] != ast_diag["selected_heldout"]

    return {
        "task_id": pool.task_id,
        "prompt_condition": pool.prompt_condition,
        "candidate_count": len(pool.candidates),
        "candidate_hashes": [c["hash"] for c in pool.candidates],
        "ast_scores": [c["ast_score"] for c in pool.candidates],
        "public_verdicts": [c["public_passed"] for c in pool.candidates],
        "heldout_verdicts": [c["heldout_passed"] for c in pool.candidates],
        "selectors": {
            "greedy": {
                "selected_index": greedy_idx,
                "heldout_passed": greedy_diag["selected_heldout"],
                "diagnosis": greedy_diag["verdict"],
            },
            "ast_ranked": {
                "selected_index": ast_idx,
                "heldout_passed": ast_diag["selected_heldout"],
                "diagnosis": ast_diag["verdict"],
            },
        },
        "policy_diverged": policy_diverged,
        "outcome_diverged": outcome_diverged,
    }
