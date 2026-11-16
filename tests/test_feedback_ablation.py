import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from codepilot.agent import run_agent


class FeedbackAblationTests(unittest.TestCase):
    def fixture(self, root):
        repo = Path(root)
        (repo / "calc.py").write_text("def double(x):\n    return x\n")
        (repo / "tests").mkdir()
        (repo / "tests" / "test_smoke.py").write_text(
            "import unittest\nfrom calc import double\nclass Smoke(unittest.TestCase):\n"
            "    def test_zero(self): self.assertEqual(double(0), 0)\n")
        return repo, ("import unittest\nfrom calc import double\nclass Verify(unittest.TestCase):\n"
                      "    def test_positive(self): self.assertEqual(double(3), 6)\n")

    def test_feedback_is_supplied_only_in_feedback_condition(self):
        for enabled in (False, True):
            with self.subTest(enabled=enabled), tempfile.TemporaryDirectory() as tmp:
                repo, verification = self.fixture(tmp)
                messages_seen = []
                def fake_model(messages, **kwargs):
                    messages_seen.append([dict(m) for m in messages])
                    content = "def double(x):\n    return {}\n".format("2*x" if len(messages_seen) > 1 else "x")
                    import json
                    return json.dumps({"edits": [{"path": "calc.py", "operation": "modify", "content": content}]})
                with patch("codepilot.agent.ask_model", side_effect=fake_model):
                    result = run_agent(repo, "double values", attempts=3,
                                       verification=verification, repair_feedback=enabled)
                self.assertTrue(result["success"])
                self.assertEqual(len(messages_seen), 2)
                self.assertEqual(len(messages_seen[1]), 4 if enabled else 2)
                self.assertEqual(result["repair"]["feedback_enabled"], enabled)
                if enabled:
                    self.assertIn("AssertionError", messages_seen[1][-1]["content"])
                else:
                    self.assertEqual(messages_seen[0], messages_seen[1])

    def test_invalid_feedback_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                run_agent(tmp, "task", repair_feedback="no")
