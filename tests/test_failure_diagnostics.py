"""Offline regression checks for v1.2 per-attempt failure diagnostics."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from codepilot.agent import run_agent, parse_edits_with_format_retry


class FailureDiagnosticsTests(unittest.TestCase):
    def test_format_retry_count(self):
        messages = [{"role": "user", "content": "task"}]
        repaired = json.dumps({"edits": [{"path": "app.py", "operation": "modify", "content": "x = 1\n"}]})
        metrics = {}
        with patch("codepilot.agent.ask_model", return_value=repaired) as mock:
            result = parse_edits_with_format_retry(messages, "{broken", diagnostics=metrics)
        self.assertEqual(len(result["edits"]), 1)
        self.assertEqual(metrics["format_retries_used"], 1)
        self.assertEqual(mock.call_count, 1)

    def test_malformed_json_then_success(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            (repo / "app.py").write_text("def value():\n    return 0\n")
            (repo / "tests").mkdir()
            (repo / "tests" / "test_app.py").write_text(
                "import unittest\nfrom app import value\n"
                "class TestApp(unittest.TestCase):\n"
                "    def test_value(self):\n        self.assertEqual(value(), 1)\n"
            )
            good = json.dumps({"edits": [{"path": "app.py", "operation": "modify", "content": "def value():\n    return 1\n"}]})
            with patch("codepilot.agent.ask_model", side_effect=["{broken", "{still broken", "{also broken", good]):
                result = run_agent(repo, "Fix value", attempts=2)
            self.assertTrue(result["success"])
            first, second = result["history"]
            self.assertEqual(first["failure_category"], "malformed_edit_json")
            self.assertEqual(first["failure_stage"], "edit_json")
            self.assertEqual(first["format_retries_used"], 2)
            self.assertIsNone(second["failure_category"])
            self.assertEqual(second["format_retries_used"], 0)
            self.assertGreaterEqual(first["elapsed_seconds"], 0)
            self.assertIn("return 0", (repo / "app.py").read_text())


if __name__ == "__main__":
    unittest.main()
