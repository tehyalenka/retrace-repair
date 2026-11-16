import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from codepilot.agent import run_agent
from backend.app import RunRequest


class CounterfactualRepairTests(unittest.TestCase):
    def test_counterfactual_retry_uses_evidence_and_original_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / 'calc.py').write_text('def double(x):\n    return x\n')
            (repo / 'tests').mkdir()
            (repo / 'tests' / 'test_smoke.py').write_text(
                'import unittest\nfrom calc import double\n'
                'class Smoke(unittest.TestCase):\n'
                '    def test_zero(self): self.assertEqual(double(0), 0)\n')
            verify = ('import unittest\nfrom calc import double\n'
                      'class Verify(unittest.TestCase):\n'
                      '    def test_positive(self): self.assertEqual(double(3), 6)\n')
            seen = []
            def model(messages, **kwargs):
                seen.append([dict(m) for m in messages])
                source = 'def double(x):\n    return x\n' if len(seen) == 1 else 'def double(x):\n    return x * 2\n'
                return json.dumps({'edits': [{'path': 'calc.py', 'operation': 'modify', 'content': source}]})
            with patch('codepilot.agent.ask_model', side_effect=model):
                result = run_agent(repo, 'double values', attempts=2,
                                   verification=verify, repair_policy='counterfactual')
            self.assertTrue(result['success'])
            self.assertEqual(result['repair']['policy'], 'counterfactual')
            self.assertEqual(len(result['history']), 2)
            self.assertIn('Counterfactual repair', seen[1][-1]['content'])
            self.assertIn('independent_verification', seen[1][-1]['content'])
            self.assertIn('ORIGINAL repository snapshot', seen[1][-1]['content'])
            self.assertEqual((repo / 'calc.py').read_text(), 'def double(x):\n    return x\n')

    def test_invalid_policy_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'repair_policy'):
                run_agent(tmp, 'task', repair_policy='unknown')

    def test_api_request_policy(self):
        self.assertEqual(RunRequest(task='fix bug', repair_policy='counterfactual').repair_policy,
                         'counterfactual')
