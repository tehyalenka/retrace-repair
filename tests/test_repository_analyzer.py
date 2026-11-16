import tempfile
import unittest
from pathlib import Path
from codepilot.repository_analyzer import discover_python_files, inspect_file, retrieve_context
from codepilot.agent import apply_edits, parse_edits


class AnalyzerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        (self.repo / "auth").mkdir()
        (self.repo / ".venv").mkdir()
        (self.repo / "auth" / "login.py").write_text("import os\ndef login(user):\n    return user\n")
        (self.repo / ".venv" / "ignore.py").write_text("x=1")

    def tearDown(self):
        self.tmp.cleanup()

    def test_discovery(self):
        self.assertEqual(discover_python_files(self.repo), ["auth/login.py"])

    def test_ast(self):
        info = inspect_file(self.repo, "auth/login.py")
        self.assertEqual(info["functions"][0]["name"], "login")
        self.assertIn("os", info["imports"])

    def test_context(self):
        self.assertIn("def login", retrieve_context(self.repo, "fix login"))

    def test_reject_unauthorized_edits(self):
        with self.assertRaises(ValueError):
            apply_edits(self.repo, [{"path": "../../escape.py", "content": "x=1"}], {"auth/login.py"})

    def test_apply_edit(self):
        changed = apply_edits(self.repo, [{"path": "auth/login.py", "content": "x=1\n"}], {"auth/login.py"})
        self.assertEqual(changed, ["auth/login.py"])

    def test_parse_json(self):
        self.assertEqual(parse_edits('{"edits": []}')["edits"], [])


if __name__ == "__main__":
    unittest.main()
