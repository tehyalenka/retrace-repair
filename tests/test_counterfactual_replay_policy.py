import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from codepilot.agent import run_agent, run_tests
from codepilot.counterfactual_replay import (
    compare_candidates,
    replay_candidate,
    replay_alternatives,
)
from codepilot.replay_generation import generate_replay_candidates
from codepilot.replay_strategy import evaluate_replay_strategy
try:
    from backend.app import RunRequest
    HAS_BACKEND = True
except ImportError:
    HAS_BACKEND = False
    RunRequest = None
from src.codepilot.cli import main as cli_main


class CounterfactualReplayPolicyTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / "repo"
        self.repo.mkdir()
        (self.repo / "calc.py").write_text("def double(x):\n    return x\n", encoding="utf-8")
        tests_dir = self.repo / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_smoke.py").write_text(
            "import unittest\nfrom calc import double\n"
            "class Smoke(unittest.TestCase):\n"
            "    def test_zero(self): self.assertEqual(double(0), 0)\n",
            encoding="utf-8",
        )

    def test_run_tests_rejects_all_skipped_suite(self):
        with tempfile.TemporaryDirectory() as tmp:
            t_dir = Path(tmp) / "tests"
            t_dir.mkdir()
            (t_dir / "test_skip.py").write_text(
                "import unittest\n"
                "class S(unittest.TestCase):\n"
                "    @unittest.skip('not implemented')\n"
                "    def test_one(self): pass\n",
                encoding="utf-8",
            )
            result = run_tests(tmp)
            self.assertFalse(result["passed"])
            self.assertEqual(result["tests_run"], 1)

    def test_replay_candidate_with_valid_and_failing_edits(self):
        passing_edits = [{
            "path": "calc.py",
            "operation": "modify",
            "content": "def double(x):\n    return x * 2\n",
        }]
        res_pass = replay_candidate(self.repo, passing_edits)
        self.assertTrue(res_pass["passed"])
        self.assertIn("calc.py", res_pass["changed_files"])
        self.assertEqual(res_pass["tests_run"], 1)

        failing_edits = [{
            "path": "calc.py",
            "operation": "modify",
            "content": "def double(x):\n    return x + 1\n", # fails double(0) == 0
        }]
        res_fail = replay_candidate(self.repo, failing_edits)
        self.assertFalse(res_fail["passed"])
        self.assertEqual(res_fail["failure_stage"], "smoke_tests")

    def test_replay_candidate_with_public_verifier_path_and_source_string(self):
        # As a source string
        verifier_source = (
            "import unittest\nfrom calc import double\n"
            "class Verifier(unittest.TestCase):\n"
            "    def test_positive(self): self.assertEqual(double(3), 6)\n"
        )
        edits = [{"path": "calc.py", "operation": "modify", "content": "def double(x):\n    return x * 2\n"}]
        res_str = replay_candidate(self.repo, edits, public_verifier=verifier_source)
        self.assertTrue(res_str["passed"])

        # As a file path
        v_file = Path(self.tmp.name) / "verifier.py"
        v_file.write_text(verifier_source, encoding="utf-8")
        res_file = replay_candidate(self.repo, edits, public_verifier=str(v_file))
        self.assertTrue(res_file["passed"])

    def test_compare_candidates_selection(self):
        results = [
            {"candidate_index": 0, "passed": False, "tests_run": 1},
            {"candidate_index": 1, "passed": True, "tests_run": 1},
        ]
        cmp_res = compare_candidates(results)
        self.assertEqual(cmp_res["selected_index"], 1)
        self.assertEqual(cmp_res["passing_indices"], [1])

        all_fail = [
            {"candidate_index": 0, "passed": False},
            {"candidate_index": 1, "passed": False},
        ]
        cmp_fail = compare_candidates(all_fail)
        self.assertIsNone(cmp_fail["selected_index"])
        self.assertEqual(cmp_fail["passing_indices"], [])

    def test_generate_replay_candidates_no_consecutive_user_messages(self):
        messages = [
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "Task: fix calc"},
        ]
        captured_messages = []

        def mock_ask(msgs, **kwargs):
            captured_messages.append([dict(m) for m in msgs])
            return json.dumps({
                "reasoning_summary": "Test candidate",
                "edits": [{"path": "calc.py", "operation": "modify", "content": "def double(x):\n    return x * 2\n"}],
            })

        with patch("codepilot.agent.ask_model", side_effect=mock_ask):
            gen = generate_replay_candidates(messages, candidate_count=2, temperature=0.5)

        self.assertEqual(gen["candidate_count"], 2)
        # Verify that candidate_messages does not have consecutive user messages
        for msg_list in captured_messages:
            roles = [m["role"] for m in msg_list]
            for i in range(len(roles) - 1):
                self.assertFalse(roles[i] == "user" and roles[i+1] == "user", f"Consecutive user roles: {roles}")

    def test_run_agent_counterfactual_replay_success_and_accounting(self):
        def model_response(messages, **kwargs):
            return json.dumps({
                "reasoning_summary": "Replay candidate",
                "edits": [{"path": "calc.py", "operation": "modify", "content": "def double(x):\n    return x * 2\n"}],
            })

        with patch("codepilot.agent.ask_model", side_effect=model_response):
            result = run_agent(
                self.repo,
                "Implement double",
                attempts=2,
                repair_policy="counterfactual_replay",
            )

        self.assertTrue(result["success"])
        self.assertEqual(result["repair"]["policy"], "counterfactual_replay")
        accounting = result["replay_accounting"]
        self.assertIsNotNone(accounting)
        self.assertGreaterEqual(accounting["model_requests_reported"], 2)
        self.assertGreaterEqual(accounting["candidate_replay_executions"], 1)

    def test_run_agent_counterfactual_replay_both_fail_and_retry(self):
        calls = []

        def model_response(messages, **kwargs):
            calls.append([dict(m) for m in messages])
            # First round: both candidates fail
            if len(calls) <= 2:
                source = "def double(x):\n    return x + 10\n"
            else:
                source = "def double(x):\n    return x * 2\n"
            return json.dumps({
                "reasoning_summary": "Attempt",
                "edits": [{"path": "calc.py", "operation": "modify", "content": source}],
            })

        with patch("codepilot.agent.ask_model", side_effect=model_response):
            result = run_agent(
                self.repo,
                "Implement double",
                attempts=2,
                repair_policy="counterfactual_replay",
            )

        self.assertTrue(result["success"])
        self.assertEqual(len(result["history"]), 2)
        self.assertFalse(result["history"][0]["passed"])
        self.assertTrue(result["history"][1]["passed"])

    @unittest.skipUnless(HAS_BACKEND, "Backend dependencies not installed")
    def test_backend_app_accepts_counterfactual_replay_policy(self):
        req = RunRequest(task="fix bug", repair_policy="counterfactual_replay")
        self.assertEqual(req.repair_policy, "counterfactual_replay")

    def test_cli_accepts_repair_policy_flag(self):
        import sys
        with patch.object(sys, "argv", ["codepilot", "agent", str(self.repo), "fix bug", "--repair-policy", "counterfactual_replay"]):
            with patch("src.codepilot.cli.run_agent") as mock_run:
                mock_run.return_value = {"success": True, "history": []}
                with patch("pathlib.Path.write_text"):
                    cli_main()
                mock_run.assert_called_once()
                self.assertEqual(mock_run.call_args[1]["repair_policy"], "counterfactual_replay")


if __name__ == "__main__":
    unittest.main()
