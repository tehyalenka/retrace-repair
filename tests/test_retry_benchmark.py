"""Deterministic, API-free benchmark of failure feedback and recovery."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from codepilot.agent import run_agent


class RetryBenchmarkTests(unittest.TestCase):
    def test_smoke_failure_then_recovery_and_exhaustion(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            (repo / "calculator.py").write_text("def double(n):\n    return n\n", encoding="utf-8")
            (repo / "tests").mkdir()
            (repo / "tests/test_calculator.py").write_text(
                "import unittest\nfrom calculator import double\n"
                "class CalculatorTests(unittest.TestCase):\n"
                "    def test_double(self): self.assertEqual(double(4), 8)\n",
                encoding="utf-8",
            )
            bad = json.dumps({"edits": [{"path": "calculator.py", "operation": "modify",
                                          "content": "def double(n):\n    return n + 1\n"}]})
            good = json.dumps({"edits": [{"path": "calculator.py", "operation": "modify",
                                           "content": "def double(n):\n    return n * 2\n"}]})
            with patch("codepilot.agent.ask_model", side_effect=[bad, good]) as model:
                result = run_agent(repo, "Fix double", attempts=2)
            self.assertTrue(result["success"])
            self.assertEqual([h["passed"] for h in result["history"]], [False, True])
            self.assertIn("Tests/validation failed", model.call_args_list[1].args[0][-1]["content"])
            self.assertIn("ORIGINAL repository snapshot", model.call_args_list[1].args[0][-1]["content"])
            self.assertEqual((repo / "calculator.py").read_text(), "def double(n):\n    return n\n")
            with patch("codepilot.agent.ask_model", return_value=bad) as model:
                exhausted = run_agent(repo, "Fix double", attempts=2)
            self.assertFalse(exhausted["success"])
            self.assertEqual(len(exhausted["history"]), 2)
            self.assertEqual(model.call_count, 2)
            self.assertEqual((repo / "calculator.py").read_text(), "def double(n):\n    return n\n")


if __name__ == "__main__":
    unittest.main()
