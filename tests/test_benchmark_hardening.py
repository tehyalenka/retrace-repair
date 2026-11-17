"""Offline adversarial checks: fixture isolation, mutation sensitivity, and reporting."""
import ast
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from benchmarks.v18 import hardening
from benchmarks.v18 import task_suite_runner as suite


class HardeningTests(unittest.TestCase):
    def test_manifest_paths_are_local_and_unique(self):
        ids = set()
        for item in suite.tasks():
            self.assertNotIn(item['id'], ids)
            ids.add(item['id'])
            for field in ('repo', 'solution', 'public_verifier', 'heldout_verifier'):
                relative = Path(item[field])
                self.assertFalse(relative.is_absolute())
                self.assertNotIn('..', relative.parts)
                resolved = (suite.ROOT / relative).resolve()
                self.assertTrue(resolved.is_relative_to(suite.ROOT.resolve()))
                self.assertTrue(resolved.exists())
            self.assertNotEqual(item['public_verifier'], item['heldout_verifier'])

    def test_fixture_never_copies_heldout_verifier(self):
        for item in suite.tasks():
            with self.subTest(task=item['id']), tempfile.TemporaryDirectory() as temp:
                repo = suite.fixture(item, Path(temp) / 'repo')
                self.assertEqual(
                    (repo / 'tests' / 'test_public.py').read_text(encoding='utf-8'),
                    (suite.ROOT / item['public_verifier']).read_text(encoding='utf-8'),
                )
                self.assertFalse((repo / 'tests' / 'heldout.py').exists())
                self.assertFalse((repo / 'tests' / 'test_heldout.py').exists())
                self.assertFalse((repo / 'solution').exists())

    def test_mutation_preserves_parseability_and_is_not_a_noop(self):
        source = 'def calculate(x):\n    return x + 1\n'
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / 'sample.py'
            file.write_text(source)
            self.assertEqual(hardening.mutate_solution(Path(temp)), 'sample.py')
            modified = file.read_text()
            self.assertNotEqual(source, modified)
            ast.parse(modified)
            self.assertIn('return None', modified)

    def test_all_reference_solutions_and_semantic_mutants(self):
        with patch('codepilot.agent.requests.post', side_effect=AssertionError('No network allowed')):
            report = hardening.run()
        self.assertEqual(report['tasks'], 15)
        self.assertEqual(len(report['rows']), 15)
        for row in report['rows']:
            with self.subTest(task=row['task']):
                self.assertTrue(row['reference_public_pass'])
                self.assertTrue(row['reference_heldout_pass'])
                self.assertTrue(row['public_killed'] or row['heldout_killed'],
                                'Both verifiers missed the injected semantic defect')

    def test_report_is_json_serializable_and_does_not_claim_model_success(self):
        with patch.object(hardening, 'audit_task', return_value={
            'task': 'example', 'category': 'bugfix', 'mutated_file': 'x.py',
            'reference_public_pass': True, 'reference_heldout_pass': True,
            'mutant_public_pass': False, 'mutant_heldout_pass': True,
            'public_killed': True, 'heldout_killed': False,
        }), patch.object(hardening, 'tasks', return_value=[{'id': 'example'}]):
            report = hardening.run()
        self.assertEqual(report['public_killed'], 1)
        self.assertEqual(report['heldout_killed'], 0)
        self.assertEqual(report['both_killed'], 0)
        self.assertEqual(report['surviving_both'], [])
        self.assertIn('not establish model repair capability', json.dumps(report))


if __name__ == '__main__':
    unittest.main()
