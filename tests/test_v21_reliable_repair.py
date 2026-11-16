import json
import tempfile
import unittest
from pathlib import Path
from benchmarks.v21.reliable_repair import evaluate, jobs_for

class V21Tests(unittest.TestCase):
    def test_offline_all_cases(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / 'report.json')
            result = evaluate(cases=['feature', 'bugfix', 'refactor'], repeats=1,
                              output=path, cooldown=0)
            self.assertEqual(result['status'], 'complete')
            self.assertEqual(sum(len(c['rows']) for c in result['cases']), 6)
            self.assertEqual(result['summary']['feedback']['successful_repairs'], 3)
            self.assertEqual(json.loads(Path(path).read_text())['status'], 'complete')

    def test_resume_only_rate_limited_arm(self):
        calls = []
        def fake(case, offline, attempts, condition_order):
            arm = condition_order[0]
            calls.append(arm)
            fail = arm == 'feedback' and calls.count('feedback') == 1
            return {'case': case, 'rows': [{'condition': arm, 'provider_failure': fail,
                    'success': not fail, 'fresh_model_calls': 0 if fail else 1,
                    'history': [{'output': 'LLM API HTTP 429 after 3 retries'}] if fail else []}]}
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / 'r.json')
            first = evaluate(mode='live', cases=['feature'], repeats=1,
                             output=path, runner=fake, cooldown=0)
            self.assertEqual(first['status'], 'paused_rate_limit')
            second = evaluate(mode='live', cases=['feature'], repeats=1,
                              output=path, runner=fake, resume=True, cooldown=0)
            self.assertEqual(second['status'], 'complete')
            self.assertEqual(second['summary']['feedback']['trials'], 1)
            self.assertEqual(second['summary']['resample']['trials'], 1)
            self.assertEqual(len(calls), 3)

    def test_mismatched_resume_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / 'r.json')
            evaluate(cases=['feature'], repeats=1, output=path)
            with self.assertRaises(ValueError):
                evaluate(cases=['feature'], repeats=2, output=path, resume=True)

if __name__ == '__main__':
    unittest.main()
