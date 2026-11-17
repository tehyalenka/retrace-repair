"""Comprehensive edit safety tests verifying containment, traversal rejection, and rollback."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from codepilot.agent import apply_edits


class EditSafetyTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name).resolve()
        self.sample_file = self.workspace / "calc.py"
        self.sample_file.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
        self.allowed = ["calc.py"]

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_path_traversal_double_dot_rejected(self):
        malicious_edits = [
            {"path": "../outside.py", "operation": "create", "content": "x = 1\n"}
        ]
        with self.assertRaises(ValueError) as ctx:
            apply_edits(self.workspace, malicious_edits, self.allowed)
        self.assertIn("Unsafe or duplicate file path", str(ctx.exception))

    def test_nested_path_traversal_rejected(self):
        malicious_edits = [
            {"path": "sub/../../escape.py", "operation": "create", "content": "x = 1\n"}
        ]
        with self.assertRaises(ValueError) as ctx:
            apply_edits(self.workspace, malicious_edits, self.allowed)
        self.assertIn("Unsafe or duplicate file path", str(ctx.exception))

    def test_absolute_path_rejected(self):
        malicious_edits = [
            {"path": "/tmp/forbidden.py", "operation": "create", "content": "x = 1\n"}
        ]
        with self.assertRaises(ValueError) as ctx:
            apply_edits(self.workspace, malicious_edits, self.allowed)
        self.assertIn("Unsafe or duplicate file path", str(ctx.exception))

    def test_non_python_extension_rejected(self):
        non_python_edits = [
            {"path": "script.sh", "operation": "create", "content": "echo bad\n"}
        ]
        with self.assertRaises(ValueError) as ctx:
            apply_edits(self.workspace, non_python_edits, self.allowed)
        self.assertIn("Unsafe or duplicate file path", str(ctx.exception))

    def test_symlink_target_rejected(self):
        target_outside = Path(tempfile.gettempdir()) / "outside_target.py"
        target_outside.write_text("secret = 42\n", encoding="utf-8")
        try:
            symlink_file = self.workspace / "link.py"
            os.symlink(target_outside, symlink_file)
            edits = [
                {"path": "link.py", "operation": "modify", "content": "secret = 0\n"}
            ]
            with self.assertRaises(ValueError) as ctx:
                apply_edits(self.workspace, edits, ["link.py"])
            self.assertIn("Symlink", str(ctx.exception))
        finally:
            if target_outside.exists():
                target_outside.unlink()

    def test_unauthorized_existing_file_operation_rejected(self):
        unauthorized_edits = [
            {"path": "calc.py", "operation": "modify", "content": "def add(a, b): return 0\n"}
        ]
        with self.assertRaises(ValueError) as ctx:
            apply_edits(self.workspace, unauthorized_edits, allowed=[])
        self.assertIn("Unauthorized existing-file operation", str(ctx.exception))

    def test_atomic_rollback_on_write_failure(self):
        initial_content = "def add(a, b):\n    return a + b\n"
        self.sample_file.write_text(initial_content, encoding="utf-8")

        second_file = self.workspace / "helper.py"
        second_file.write_text("def helper(): pass\n", encoding="utf-8")
        allowed = ["calc.py", "helper.py"]

        edits = [
            {"path": "calc.py", "operation": "modify", "content": "def add(a, b): return a * b\n"},
            {"path": "helper.py", "operation": "modify", "content": "def helper(): return True\n"},
        ]

        original_write_text = Path.write_text

        def failing_write_text(path_self, *args, **kwargs):
            if "helper.py" in str(path_self):
                raise OSError("Simulated disk write failure on helper.py")
            return original_write_text(path_self, *args, **kwargs)

        with patch.object(Path, "write_text", autospec=True, side_effect=failing_write_text):
            with self.assertRaises(OSError):
                apply_edits(self.workspace, edits, allowed)

        self.assertEqual(self.sample_file.read_text(encoding="utf-8"), initial_content)

    def test_atomic_rollback_unlinks_newly_created_files(self):
        new_file = self.workspace / "new_module.py"
        self.assertFalse(new_file.exists())

        edits = [
            {"path": "new_module.py", "operation": "create", "content": "class A: pass\n"},
            {"path": "calc.py", "operation": "modify", "content": "def add(a, b): return 0\n"},
        ]

        original_write_text = Path.write_text

        def failing_write_text(path_self, *args, **kwargs):
            if "calc.py" in str(path_self):
                raise OSError("Simulated disk write failure on calc.py")
            return original_write_text(path_self, *args, **kwargs)

        with patch.object(Path, "write_text", autospec=True, side_effect=failing_write_text):
            with self.assertRaises(OSError):
                apply_edits(self.workspace, edits, ["calc.py"])

        self.assertFalse(new_file.exists())


if __name__ == "__main__":
    unittest.main()
