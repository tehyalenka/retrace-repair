import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from codepilot.agent import run_agent, generate_task_tests


class GeneratedVerificationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'feature.py').write_text('def double(n): return n\n')
        (self.root / 'tests').mkdir()
        (self.root / 'tests' / 'test_smoke.py').write_text(
            'import unittest\nclass Smoke(unittest.TestCase):\n'
            '    def test_import(self): import feature\n')
        self.tests = ('import unittest\nfrom feature import double\n'
                      'class Feature(unittest.TestCase):\n'
                      '    def test_double(self): self.assertEqual(double(4), 8)\n')

    def test_failure_feedback_causes_repair(self):
        wrong = json.dumps({'edits': [{'path': 'feature.py', 'content': 'def double(n): return n\n'}]})
        fixed = json.dumps({'edits': [{'path': 'feature.py', 'content': 'def double(n): return n * 2\n'}]})
        with patch('codepilot.agent.ask_model', side_effect=[json.dumps({'tests': self.tests}), wrong, fixed]) as model:
            result = run_agent(self.root, 'fix double', attempts=2, generate_tests=True)
        self.assertTrue(result['success'], result)
        self.assertEqual(len(result['history']), 2)
        self.assertFalse(result['history'][0]['passed'])
        self.assertTrue(result['history'][1]['generated_tests_passed'])
        self.assertEqual(model.call_count, 3)
        self.assertEqual((self.root / 'feature.py').read_text(), 'def double(n): return n\n')

    def test_generation_failure_is_not_success(self):
        with patch('codepilot.agent.ask_model', return_value='not json') as model:
            result = run_agent(self.root, 'fix double', generate_tests=True)
        self.assertFalse(result['success'])
        self.assertEqual(result['history'], [])
        self.assertEqual(model.call_count, 3)

    def test_reject_empty_generated_tests(self):
        with patch('codepilot.agent.ask_model', return_value=json.dumps({'tests': 'import unittest\n'})):
            with self.assertRaises(ValueError):
                generate_task_tests('fix', 'map', 'context')

    def test_default_compatibility(self):
        response = json.dumps({'edits': [{'path': 'feature.py', 'content': 'def double(n): return n * 2\n'}]})
        with patch('codepilot.agent.ask_model', return_value=response):
            result = run_agent(self.root, 'fix double')
        self.assertTrue(result['success'])
        self.assertEqual(result['generated_test_status'], 'disabled')


class GeneratedTestParsingTests(unittest.TestCase):
    def test_double_escaped_newlines_are_recovered(self):
        source = 'import unittest\nclass Checks(unittest.TestCase):\n    def test_ok(self): self.assertTrue(True)\n'
        double_escaped = source.replace('\n', '\\n')
        with patch('codepilot.agent.ask_model', return_value=json.dumps({'tests': double_escaped})) as model:
            result = generate_task_tests('task', 'map', 'context')
        self.assertEqual(result, source)
        self.assertEqual(model.call_count, 1)

    def test_malformed_source_retried(self):
        source = 'import unittest\nclass Checks(unittest.TestCase):\n    def test_ok(self): self.assertTrue(True)\n'
        with patch('codepilot.agent.ask_model', side_effect=[json.dumps({'tests': 'def broken(\n'}), json.dumps({'tests': source})]) as model:
            result = generate_task_tests('task', 'map', 'context')
        self.assertEqual(result, source)
        self.assertEqual(model.call_count, 2)
