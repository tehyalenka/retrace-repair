"""Adversarial verification checks. Offline, standard library only."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from benchmarks.v18 import task_suite_runner as suite


class VerifierAdversarialTests(unittest.TestCase):
    def _verify(self, source, files=None):
        with tempfile.TemporaryDirectory(prefix='retrace-verifier-') as tmp:
            repo = Path(tmp)
            for name, contents in (files or {}).items():
                target = repo / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(contents, encoding='utf-8')
            with patch('codepilot.agent.requests.post', side_effect=AssertionError('No provider calls')):
                return suite.verify(repo, source)

    def test_empty_test_file_cannot_pass(self):
        self.assertFalse(self._verify(''))

    def test_helper_only_test_file_cannot_pass(self):
        self.assertFalse(self._verify('def helper():\n    return True\n'))

    def test_skipped_test_does_not_count_as_proof_of_correctness(self):
        self.assertFalse(self._verify('import unittest\nclass T(unittest.TestCase):\n @unittest.skip("not ready")\n def test_case(self): pass\n'))

    def test_actual_failing_test_is_rejected(self):
        self.assertFalse(self._verify('import unittest\nclass T(unittest.TestCase):\n def test_bad(self): self.assertEqual(1, 2)\n'))

    def test_actual_passing_test_is_accepted(self):
        self.assertTrue(self._verify('import unittest\nclass T(unittest.TestCase):\n def test_good(self): self.assertEqual(2, 2)\n'))

    def test_syntax_error_is_rejected(self):
        self.assertFalse(self._verify('def test_broken(:\n pass\n'))

    def test_import_error_is_rejected(self):
        self.assertFalse(self._verify('import module_that_does_not_exist_retrace\n'))

    def test_manifest_reference_solutions_still_verify(self):
        for item in suite.tasks():
            with self.subTest(task=item['id']):
                repo = suite.ROOT / item['solution']
                public = (suite.ROOT / item['public_verifier']).read_text(encoding='utf-8')
                hidden = (suite.ROOT / item['heldout_verifier']).read_text(encoding='utf-8')
                self.assertTrue(suite.verify(repo, public))
                self.assertTrue(suite.verify(repo, hidden))


if __name__ == '__main__':
    unittest.main()
