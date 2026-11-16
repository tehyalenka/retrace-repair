import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from benchmarks.v27 import challenging_recovery as v27

class V27MultiFileTests(unittest.TestCase):
    def test_tasks_are_distinct_and_multifile(self):
        tasks = json.loads((v27.HERE / 'tasks.json').read_text())
        self.assertEqual(set(tasks), set(v27.CASES))
        for case in v27.CASES:
            self.assertIn('Both ', tasks[case])
            self.assertGreaterEqual(len(list((v27.HERE / 'cases' / case).glob('*.py'))), 3)
    def test_live_setup_and_hidden_verifiers(self):
        for case in v27.CASES:
            with tempfile.TemporaryDirectory() as temp:
                repo, task, verifier = v27.setup('live', case, temp)
                self.assertTrue(repo.is_dir())
                self.assertTrue(task)
                self.assertIn('unittest', verifier)
    def test_offline_fixture_no_provider(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, task, verifier = v27.setup('offline', 'pricing', temp)
            self.assertTrue(repo.exists())
            self.assertIn('double', task)
    def test_unknown_case_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                v27.setup('live', 'unknown', temp)
