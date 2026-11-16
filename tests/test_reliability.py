import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from codepilot.agent import apply_edits, run_tests, run_agent, parse_edits_with_format_retry


class ReliabilityTests(unittest.TestCase):
    def test_atomic_validation(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "a.py").write_text("x = 1\n")
            with self.assertRaises(ValueError):
                apply_edits(repo, [
                    {"path": "a.py", "content": "x = 2\n"},
                    {"path": "bad.py", "content": "y = 2\n"},
                ], {"a.py"})
            self.assertEqual((repo / "a.py").read_text(), "x = 1\n")

    def test_retry_recreates_new_module_from_original_snapshot(self):
        import json
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "auth.py").write_text("def authenticate():\n    return True\n")
            (repo / "tests").mkdir()
            (repo / "tests/test_smoke.py").write_text(
                "import unittest\nclass Smoke(unittest.TestCase):\n"
                "    def test_one(self): self.assertTrue(True)\n")
            verifier = ("import unittest\nfrom permissions import can_edit\n"
                        "class Verify(unittest.TestCase):\n"
                        "    def test_admin(self): self.assertTrue(can_edit('admin', False))\n")
            bad = "def can_edit(role, owner):\n    return False\n"
            good = "def can_edit(role, owner):\n    return role == 'admin' or owner\n"
            def response(content):
                return json.dumps({"edits": [
                    {"path": "permissions.py", "operation": "create", "content": content},
                    {"path": "auth.py", "operation": "modify", "content":
                     "from permissions import can_edit\ndef authenticate():\n    return True\n"}
                ]})
            with patch("codepilot.agent.ask_model", side_effect=[response(bad), response(good)]) as mock:
                result = run_agent(repo, "add permissions", attempts=2, verification=verifier)
            self.assertTrue(result["success"], result)
            self.assertEqual(len(result["history"]), 2)
            self.assertFalse(result["history"][0]["passed"])
            self.assertIn("permissions.py", result["history"][1]["changed_files"])
            self.assertIn("ORIGINAL repository snapshot", mock.call_args_list[1].args[0][-1]["content"])
            self.assertFalse((repo / "permissions.py").exists())

    def test_invalid_edit_json_is_reformatted_without_consuming_attempt(self):
        import json
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "calc.py").write_text("def calc(x):\n    return x\n")
            (repo / "tests").mkdir()
            (repo / "tests/test_calc.py").write_text(
                "import unittest\nfrom calc import calc\nclass TestCalc(unittest.TestCase):\n"
                "    def test_double(self): self.assertEqual(calc(2), 4)\n")
            good = json.dumps({"edits": [{"path": "calc.py", "operation": "modify",
                                         "content": "def calc(x):\n    return x * 2\n"}]})
            with patch("codepilot.agent.ask_model", side_effect=['{"edits": [', good]) as mock:
                result = run_agent(repo, "double", attempts=1)
            self.assertTrue(result["success"], result)
            self.assertEqual(len(result["history"]), 1)
            self.assertEqual(mock.call_count, 2)
            self.assertEqual((repo / "calc.py").read_text(), "def calc(x):\n    return x\n")

    def test_non_object_edit_is_reformatted_without_consuming_attempt(self):
        import json
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "calc.py").write_text("def calc(x):\n    return x\n")
            (repo / "tests").mkdir()
            (repo / "tests/test_calc.py").write_text(
                "import unittest\nfrom calc import calc\nclass TestCalc(unittest.TestCase):\n"
                "    def test_double(self): self.assertEqual(calc(2), 4)\n")
            bad = json.dumps({"edits": ["calc.py", "def calc(x): return x * 2"]})
            good = json.dumps({"edits": [{"path": "calc.py", "operation": "modify",
                                         "content": "def calc(x):\n    return x * 2\n"}]})
            with patch("codepilot.agent.ask_model", side_effect=[bad, good]) as mock:
                result = run_agent(repo, "double", attempts=1)
            self.assertTrue(result["success"], result)
            self.assertEqual(len(result["history"]), 1)
            self.assertEqual(mock.call_count, 2)

    def test_missing_edit_content_is_reformatted(self):
        import json
        bad = json.dumps({"edits": [{"path": "calc.py", "operation": "modify"}]})
        good = json.dumps({"edits": [{"path": "calc.py", "operation": "modify", "content": "x = 2\n"}]})
        with patch("codepilot.agent.ask_model", return_value=good) as mock:
            parsed = parse_edits_with_format_retry([], bad)
        self.assertEqual(parsed["edits"][0]["content"], "x = 2\n")
        mock.assert_called_once()

    def test_edit_json_retry_exhaustion(self):
        with patch("codepilot.agent.ask_model", side_effect=['{', '{']):
            with self.assertRaisesRegex(ValueError, "formatting retries"):
                parse_edits_with_format_retry([], '{', format_retries=2)

    def test_rate_limit_retry_after(self):
        from codepilot.agent import ask_model
        from unittest.mock import Mock
        import os
        limited = Mock(status_code=429, headers={"Retry-After": "0"})
        ok = Mock(status_code=200)
        ok.json.return_value = {"choices": [{"message": {"content": "{}"}}]}
        with patch.dict(os.environ, {"GROQ_API_KEY": "test-key", "CODEPILOT_PROVIDER": "groq"}):
            with patch("codepilot.agent.requests.post", side_effect=[limited, ok]) as post:
                with patch("codepilot.agent.time.sleep") as sleep:
                    self.assertEqual(ask_model([{"role": "user", "content": "hello"}]), "{}")
        self.assertEqual(post.call_count, 2)
        sleep.assert_called_once()

    def test_rate_limit_exhaustion_is_graceful(self):
        from unittest.mock import Mock
        import os
        limited = Mock(status_code=429, headers={"Retry-After": "0"})
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "calc.py").write_text("def calc(x):\n    return x\n")
            (repo / "tests").mkdir()
            (repo / "tests/test_smoke.py").write_text(
                "import unittest\nclass Smoke(unittest.TestCase):\n"
                "    def test_ok(self): self.assertTrue(True)\n")
            with patch.dict(os.environ, {"GROQ_API_KEY": "test-key", "CODEPILOT_PROVIDER": "groq"}):
                with patch("codepilot.agent.requests.post", return_value=limited):
                    with patch("codepilot.agent.time.sleep"):
                        result = run_agent(repo, "change calc", attempts=1)
        self.assertFalse(result["success"])
        self.assertIn("HTTP 429", result["history"][0]["output"])

    def test_json_mode_opt_in(self):
        from codepilot.agent import ask_model
        from unittest.mock import Mock
        import os
        ok = Mock(status_code=200)
        ok.json.return_value = {"choices": [{"message": {"content": "{}"}}]}
        with patch.dict(os.environ, {"GROQ_API_KEY": "test-key", "CODEPILOT_PROVIDER": "groq", "CODEPILOT_JSON_MODE": "1"}):
            with patch("codepilot.agent.requests.post", return_value=ok) as post:
                ask_model([{"role": "user", "content": "json please"}])
        self.assertEqual(post.call_args.kwargs["json"]["response_format"], {"type": "json_object"})

    def test_zero_tests_fail(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "tests").mkdir()
            self.assertFalse(run_tests(d)["passed"])

    def test_verification_feedback_retries(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / "calc.py").write_text("def calc(x):\n    return x\n")
            (repo / "tests").mkdir()
            (repo / "tests/test_smoke.py").write_text(
                "import unittest\nclass Smoke(unittest.TestCase):\n"
                "    def test_one(self): self.assertTrue(True)\n")
            verifier = ("import unittest\nfrom calc import calc\n"
                        "class Verify(unittest.TestCase):\n"
                        "    def test_double(self): self.assertEqual(calc(3), 6)\n")
            answers = [
                '{"edits":[{"path":"calc.py","content":"def calc(x):\\n    return x + 1\\n"}]}',
                '{"edits":[{"path":"calc.py","content":"def calc(x):\\n    return x * 2\\n"}]}',
            ]
            # Construct valid JSON to avoid escape ambiguity.
            import json
            answers = [json.dumps({"edits": [{"path": "calc.py", "content": c}]})
                       for c in ["def calc(x):\n    return x + 1\n", "def calc(x):\n    return x * 2\n"]]
            with patch("codepilot.agent.ask_model", side_effect=answers):
                result = run_agent(repo, "double values", attempts=2, verification=verifier)
            self.assertTrue(result["success"])
            self.assertEqual(len(result["history"]), 2)
            self.assertFalse(result["history"][0]["passed"])
            self.assertTrue(result["history"][1]["passed"])
            self.assertIn("return x * 2", result["files"]["calc.py"])
            self.assertIn("return x\n", (repo / "calc.py").read_text())


if __name__ == "__main__":
    unittest.main()
