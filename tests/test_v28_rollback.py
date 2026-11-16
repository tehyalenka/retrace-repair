"""Fault-injection tests for failed multi-file writes (no provider needed)."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from codepilot.agent import apply_edits


class RollbackFaultTests(unittest.TestCase):
    def test_partial_write_restores_existing_and_removes_created(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "first.py").write_bytes(b"ORIGINAL = 1\n")
            (root / "last.py").write_bytes(b"UNCHANGED = 1\n")
            real_write = Path.write_text
            failed = [False]

            def fail_mid_write(path, content, *args, **kwargs):
                if path.name == "last.py" and not failed[0]:
                    failed[0] = True
                    real_write(path, "PARTIAL = 1\n", *args, **kwargs)
                    raise OSError("injected write failure")
                return real_write(path, content, *args, **kwargs)

            edits = [
                {"path": "first.py", "content": "NEW = 2\n"},
                {"path": "added.py", "operation": "create", "content": "CREATED = 1\n"},
                {"path": "last.py", "content": "CHANGED = 2\n"},
            ]
            with patch.object(Path, "write_text", fail_mid_write):
                with self.assertRaisesRegex(OSError, "injected write failure"):
                    apply_edits(root, edits, {"first.py", "last.py"})
            self.assertEqual((root / "first.py").read_bytes(), b"ORIGINAL = 1\n")
            self.assertEqual((root / "last.py").read_bytes(), b"UNCHANGED = 1\n")
            self.assertFalse((root / "added.py").exists())

    def test_rollback_continues_after_restore_error(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "first.py").write_bytes(b"FIRST = 1\n")
            (root / "last.py").write_bytes(b"LAST = 1\n")
            real_write_text = Path.write_text
            real_write_bytes = Path.write_bytes

            def fail_final_write(path, content, *args, **kwargs):
                if path.name == "last.py":
                    raise OSError("injected edit failure")
                return real_write_text(path, content, *args, **kwargs)

            def fail_one_restore(path, content):
                if path.name == "last.py":
                    raise OSError("injected restore failure")
                return real_write_bytes(path, content)

            edits = [
                {"path": "first.py", "content": "FIRST = 2\n"},
                {"path": "added.py", "operation": "create", "content": "NEW = 1\n"},
                {"path": "last.py", "content": "LAST = 2\n"},
            ]
            with patch.object(Path, "write_text", fail_final_write), patch.object(Path, "write_bytes", fail_one_restore):
                with self.assertRaisesRegex(OSError, "rollback incomplete for: last.py"):
                    apply_edits(root, edits, {"first.py", "last.py"})
            self.assertEqual((root / "first.py").read_bytes(), b"FIRST = 1\n")
            self.assertFalse((root / "added.py").exists())


if __name__ == "__main__":
    unittest.main()
