"""Tests for Controlled Candidate-Selection Ablation Protocol & Causal Diagnosis."""

import tempfile
import unittest
from pathlib import Path

from benchmarks.v18.candidate_selection_ablation import (
    CandidatePool,
    NO_ELIGIBLE_CANDIDATE,
    NO_VALID_CANDIDATE,
    SELECTION_FAILURE,
    SUCCESSFUL_SELECTION,
    diagnose_selection,
    evaluate_ablation_on_pool,
    select_ast_ranked,
    select_greedy,
)


class TestCandidateSelectionAblation(unittest.TestCase):
    def test_synthetic_selection_failure_disentanglement(self):
        """Synthetic fixture where C0 is held-out correct (low AST score)

        and C1 is held-out incorrect (high AST score due to syntactic bloat).
        Confirms that:
        - Greedy selector chooses C0 -> SUCCESSFUL_SELECTION
        - AST selector chooses C1 -> SELECTION_FAILURE
        - Policy and outcome divergence are detected.
        """
        pool = CandidatePool(task_id="synthetic_circuit_breaker", prompt_condition="standard")

        # C0: Minimal correct patch: passes public and held-out, simple clean code
        edits_c0 = [{
            "path": "circuit.py",
            "operation": "modify",
            "content": "def call(val):\n    if val < 0:\n        raise ValueError('negative')\n    return val * 2\n",
        }]

        # C1: Structurally bloated patch: passes public, fails held-out (e.g. raises TypeError),
        # but has multiple try/finally and extra isinstance checks giving it a higher AST score.
        edits_c1 = [{
            "path": "circuit.py",
            "operation": "modify",
            "content": (
                "def call(val):\n"
                "    try:\n"
                "        if isinstance(val, bool) or not isinstance(val, int):\n"
                "            raise TypeError('wrong type')\n"
                "        if val < 0:\n"
                "            raise ValueError('negative')\n"
                "        return val * 2\n"
                "    finally:\n"
                "        pass\n"
            ),
        }]

        pool.add_candidate(
            candidate_index=0,
            edits=edits_c0,
            reasoning_summary="Minimal clean fix",
            public_result={"passed": True, "output": "OK"},
            heldout_result={"passed": True, "output": "OK"},
        )

        pool.add_candidate(
            candidate_index=1,
            edits=edits_c1,
            reasoning_summary="Defensive structural patch with extra guards",
            public_result={"passed": True, "output": "OK"},
            heldout_result={"passed": False, "output": "FAIL: expected ValueError got TypeError"},
        )

        # Verify C1 received a higher AST score due to structural guards
        self.assertGreater(pool.candidates[1]["ast_score"], pool.candidates[0]["ast_score"])

        # Test Greedy selector: picks first passing index (C0)
        greedy_idx = select_greedy(pool)
        self.assertEqual(greedy_idx, 0)
        greedy_diag = diagnose_selection(pool, greedy_idx)
        self.assertEqual(greedy_diag["verdict"], SUCCESSFUL_SELECTION)
        self.assertTrue(greedy_diag["selected_heldout"])

        # Test AST selector: picks highest AST score passing index (C1)
        ast_idx = select_ast_ranked(pool)
        self.assertEqual(ast_idx, 1)
        ast_diag = diagnose_selection(pool, ast_idx)
        self.assertEqual(ast_diag["verdict"], SELECTION_FAILURE)
        self.assertFalse(ast_diag["selected_heldout"])

        # Test full evaluation telemetry output
        telemetry = evaluate_ablation_on_pool(pool)
        self.assertTrue(telemetry["policy_diverged"])
        self.assertTrue(telemetry["outcome_diverged"])
        self.assertEqual(telemetry["selectors"]["greedy"]["diagnosis"], SUCCESSFUL_SELECTION)
        self.assertEqual(telemetry["selectors"]["ast_ranked"]["diagnosis"], SELECTION_FAILURE)

    def test_synthetic_no_valid_candidate_generation_failure(self):
        """When neither candidate satisfies held-out tests, diagnosis is NO_VALID_CANDIDATE."""
        pool = CandidatePool(task_id="synthetic_hard_task", prompt_condition="standard")

        pool.add_candidate(
            candidate_index=0,
            edits=[{"path": "foo.py", "operation": "modify", "content": "x = 1"}],
            public_result={"passed": True},
            heldout_result={"passed": False},
        )
        pool.add_candidate(
            candidate_index=1,
            edits=[{"path": "foo.py", "operation": "modify", "content": "x = 2"}],
            public_result={"passed": True},
            heldout_result={"passed": False},
        )

        greedy_idx = select_greedy(pool)
        diag = diagnose_selection(pool, greedy_idx)
        self.assertEqual(diag["verdict"], NO_VALID_CANDIDATE)

    def test_synthetic_no_eligible_candidate_scenario(self):
        """When a candidate passes held-out tests but fails visible public tests,

        neither selector should select it, and diagnosis should be NO_ELIGIBLE_CANDIDATE.
        """
        pool = CandidatePool(task_id="synthetic_ineligible_task", prompt_condition="standard")

        # C0: Fails public tests, but passes held-out tests
        pool.add_candidate(
            candidate_index=0,
            edits=[{"path": "foo.py", "operation": "modify", "content": "x = 1"}],
            public_result={"passed": False, "output": "FAIL: smoke test failed"},
            heldout_result={"passed": True, "output": "OK"},
        )
        # C1: Fails public tests and fails held-out tests
        pool.add_candidate(
            candidate_index=1,
            edits=[{"path": "foo.py", "operation": "modify", "content": "x = 2"}],
            public_result={"passed": False, "output": "FAIL: smoke test failed"},
            heldout_result={"passed": False, "output": "FAIL"},
        )

        # Neither selector should select an ineligible candidate
        greedy_idx = select_greedy(pool)
        self.assertIsNone(greedy_idx)
        ast_idx = select_ast_ranked(pool)
        self.assertIsNone(ast_idx)

        # Diagnosis should specifically identify NO_ELIGIBLE_CANDIDATE
        greedy_diag = diagnose_selection(pool, greedy_idx)
        self.assertEqual(greedy_diag["verdict"], NO_ELIGIBLE_CANDIDATE)
        self.assertFalse(greedy_diag["selected_heldout"])

        ast_diag = diagnose_selection(pool, ast_idx)
        self.assertEqual(ast_diag["verdict"], NO_ELIGIBLE_CANDIDATE)
        self.assertFalse(ast_diag["selected_heldout"])

    def test_pool_serialization(self):
        """Ensure CandidatePool serializes and reloads deterministically."""
        pool = CandidatePool(task_id="task_abc", prompt_condition="invariant")
        pool.add_candidate(
            candidate_index=0,
            edits=[{"path": "a.py", "operation": "create", "content": "pass"}],
            public_result={"passed": True},
            heldout_result={"passed": True},
        )

        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "pool.json"
            pool.save(p)
            loaded = CandidatePool.load(p)

            self.assertEqual(loaded.task_id, "task_abc")
            self.assertEqual(loaded.prompt_condition, "invariant")
            self.assertEqual(len(loaded.candidates), 1)
            self.assertEqual(loaded.candidates[0]["hash"], pool.candidates[0]["hash"])


if __name__ == "__main__":
    unittest.main()
