import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('advanced_eval', ROOT / 'benchmarks/v11/evaluate.py')
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)

class AdvancedBenchmarkTests(unittest.TestCase):
    def test_fixtures_exist(self):
        for name in MOD.CASES:
            self.assertTrue((MOD.HERE / 'cases' / name / 'tests/test_smoke.py').is_file())
            self.assertTrue((MOD.HERE / 'hidden' / (name + '.py')).is_file())
    def test_summary_and_recovery(self):
        def fake_agent(repo, task, **kwargs):
            return {'success': True, 'files': {}, 'history': [
                {'passed': False, 'verification_passed': False},
                {'passed': True, 'verification_passed': True}]}
        with tempfile.TemporaryDirectory() as tmp:
            report = MOD.evaluate(('bugfix',), 3, False, Path(tmp)/'report.json', agent=fake_agent)
        self.assertEqual(report['summary']['recovered_after_failure'], 1)
        self.assertEqual(report['summary']['first_attempt_success_rate'], 0)
        self.assertEqual(report['summary']['success_rate'], 1)
    def test_exception_is_failure(self):
        def failing(*args, **kwargs):
            raise RuntimeError('provider unavailable')
        with tempfile.TemporaryDirectory() as tmp:
            report = MOD.evaluate(('feature',), 1, False, Path(tmp)/'report.json', agent=failing)
        self.assertEqual(report['summary']['passed'], 0)
        self.assertEqual(report['cases'][0]['attempts_used'], 0)

if __name__ == '__main__':
    unittest.main()
