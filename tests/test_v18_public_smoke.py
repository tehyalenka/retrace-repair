"""Regression tests for synthetic task smoke-test discovery."""
import tempfile
import unittest
from pathlib import Path
from benchmarks.v18.task_suite_runner import tasks, fixture
from codepilot.agent import run_tests


class PublicSmokeTests(unittest.TestCase):
    def test_every_fixture_has_discoverable_public_smoke_tests(self):
        for item in tasks():
            with self.subTest(task=item['id']), tempfile.TemporaryDirectory() as tmp:
                repo = fixture(item, Path(tmp) / 'repo')
                self.assertTrue((repo / 'tests' / 'test_public.py').is_file())
                result = run_tests(repo)
                self.assertGreater(result['tests_run'], 0, result['output'])
                self.assertFalse(result['passed'], 'Initial broken fixture should fail public tests')
                self.assertNotIn('Start directory is not importable', result['output'])
                self.assertNotIn('No tests discovered', result['output'])
