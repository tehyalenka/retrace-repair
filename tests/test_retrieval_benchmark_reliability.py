import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from codepilot import agent


class RetrievalBenchmarkReliabilityTests(unittest.TestCase):
    def test_provider_error_during_json_repair_is_classified_correctly(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'sample.py').write_text('def value():\n    return 1\n')
            (root / 'tests').mkdir()
            (root / 'tests' / 'test_smoke.py').write_text('import unittest\nclass T(unittest.TestCase):\n def test_ok(self): self.assertTrue(True)\n')
            with patch.object(agent, 'ask_model', side_effect=['not-json', agent.LLMAPIError('LLM API HTTP 429 after 3 retries; retry later')]):
                result = agent.run_agent(root, 'change value', attempts=1)
            attempt = result['history'][0]
            self.assertEqual(attempt['failure_category'], 'provider_error')
            self.assertEqual(attempt['failure_stage'], 'edit_json')
            self.assertEqual(attempt['format_retries_used'], 1)
            self.assertIn('context_files', result['retrieval'])

    def test_infrastructure_exclusion_and_cooldown(self):
        module_path = Path(__file__).resolve().parents[1] / 'benchmarks' / 'v11' / 'retrieval_experiment.py'
        spec = importlib.util.spec_from_file_location('retrieval_experiment_v141', module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        calls = []
        sleeps = []
        def fake_agent(repo, task, **kwargs):
            calls.append(kwargs['retrieval_strategy'])
            if len(calls) == 1:
                return {'success': False, 'history': [{'passed': False, 'failure_category': 'provider_error', 'output': 'LLM API HTTP 429'}]}
            return {'success': True, 'history': [{'passed': True}], 'retrieval': {'context_chars': 12, 'context_files': ['a.py']}}
        with tempfile.TemporaryDirectory() as directory:
            report = module.evaluate(1, 1, 2, directory, agent=fake_agent, cooldown=0.1, sleep=sleeps.append)
        self.assertEqual(len(sleeps), 5)
        self.assertEqual(len(report['runs']), 6)
        lexical = next(item for item in report['summary'] if item['strategy'] == 'lexical')
        self.assertEqual(lexical['infrastructure_failures'], 1)
        self.assertEqual(lexical['completed_success_rate'], 1.0)
        self.assertEqual(report['runs'][1]['retrieval']['context_chars'], 12)
