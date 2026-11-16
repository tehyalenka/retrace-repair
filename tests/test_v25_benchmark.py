"""Offline checks for the v2.5 benchmark's task/verifier contract."""
import json
import unittest
from pathlib import Path
from unittest.mock import patch

import benchmarks.v25.challenging_recovery as v25


class V25BenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old = json.loads((v25.V23 / 'tasks.json').read_text())
        cls.new = json.loads((v25.HERE / 'tasks.json').read_text())

    def test_only_checkout_prompt_changes(self):
        self.assertEqual(set(self.old), set(self.new))
        for case in ('permissions', 'eventlog'):
            self.assertEqual(self.old[case], self.new[case])
        self.assertNotEqual(self.old['checkout'], self.new['checkout'])

    def test_checkout_requirements_are_explicit(self):
        task = self.new['checkout'].lower()
        for requirement in ('nonempty', 'bool', 'duplicate', 'valueerror',
                            'payment declined', 'charge exactly once',
                            'original receipt', 'unknown skus'):
            with self.subTest(requirement=requirement):
                self.assertIn(requirement, task)

    def test_live_setup_uses_original_repo_and_verifier(self):
        for case in v25.CASES:
            with self.subTest(case=case):
                repo, task, verifier = v25.setup('live', case, None)
                self.assertEqual(repo, v25.V23 / 'cases' / case)
                self.assertEqual(task, self.new[case])
                self.assertEqual(verifier, (v25.V23 / 'hidden' / (case + '.py')).read_text())
                self.assertTrue((repo / 'tests').is_dir())

    def test_invalid_case_rejected(self):
        with self.assertRaises(ValueError):
            v25.setup('live', 'missing', None)

    def test_offline_setup_uses_original_offline_fixture(self):
        marker = object()
        with patch.object(v25, 'ORIGINAL_SETUP', return_value=marker) as original:
            self.assertIs(v25.setup('offline', 'checkout', '/tmp/example'), marker)
            original.assert_called_once_with('offline', 'bugfix', '/tmp/example')


if __name__ == '__main__':
    unittest.main()
