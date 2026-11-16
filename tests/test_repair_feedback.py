"""Offline feedback-driven repair regression tests."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from codepilot.agent import _repair_feedback, run_agent


class RepairFeedbackTests(unittest.TestCase):
    def test_feedback_uses_independent_verification_details(self):
        result = _repair_feedback({"failure_stage": "independent_verification",
                                   "failure_category": "test_failure",
                                   "changed_files": ["calc.py"],
                                   "output": "smoke passed",
                                   "verification_output": "FAIL: test_negative"})
        self.assertIn("FAIL: test_negative", result)
        self.assertIn("calc.py", result)
        self.assertNotIn("smoke passed", result)

    def test_feedback_is_bounded(self):
        result = _repair_feedback({"failure_stage": "smoke_tests",
                                   "failure_category": "test_failure",
                                   "output": "x" * 100000})
        self.assertLess(len(result), 3200)

    def test_failing_verification_triggers_diagnostic_repair(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "calc.py").write_text("def double(x):\n    return x\n")
            (repo / "tests").mkdir()
            (repo / "tests/test_smoke.py").write_text(
                "import unittest\nfrom calc import double\n"
                "class Smoke(unittest.TestCase):\n"
                "    def test_zero(self): self.assertEqual(double(0), 0)\n")
            verifier = ("import unittest\nfrom calc import double\n"
                        "class Verify(unittest.TestCase):\n"
                        "    def test_positive(self): self.assertEqual(double(3), 6)\n")
            def response(body):
                return json.dumps({"edits": [{"path": "calc.py", "operation": "modify", "content": body}]})
            bad = response("def double(x):\n    return x\n")
            good = response("def double(x):\n    return 2*x\n")
            with patch("codepilot.agent.ask_model", side_effect=[bad, good]) as model:
                result = run_agent(repo, "double values", attempts=2, verification=verifier)
            self.assertTrue(result["success"], result)
            self.assertTrue(result["repair"]["recovered"])
            self.assertEqual(result["repair"]["code_failures"], 1)
            self.assertTrue(result["history"][1]["repair_attempt"])
            prompt = model.call_args_list[1].args[0][-1]["content"]
            self.assertIn("independent_verification", prompt)
            self.assertIn("test_positive", prompt)
            self.assertEqual((repo / "calc.py").read_text(), "def double(x):\n    return x\n")

    def test_provider_error_does_not_trigger_code_repair(self):
        from codepilot.agent import LLMAPIError
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "calc.py").write_text("x = 1\n")
            with patch("codepilot.agent.ask_model", side_effect=LLMAPIError("HTTP 429")) as model:
                result = run_agent(repo, "fix", attempts=3)
            self.assertFalse(result["success"])
            self.assertEqual(model.call_count, 1)
            self.assertFalse(result["repair"]["attempted"])
            self.assertEqual(result["repair"]["provider_failures"], 1)


if __name__ == "__main__":
    unittest.main()
