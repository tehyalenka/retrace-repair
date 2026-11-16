import json
import tempfile
import unittest
from pathlib import Path
from benchmarks.v18 import research_report


class ResearchReportTests(unittest.TestCase):
    def test_pending_excluded_from_denominator_and_pairs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root / 'manifest.json'
            manifest.write_text(json.dumps({'tasks': [{'id': 'demo', 'category': 'bugfix'}]}))
            (root / 'demo-live.json').write_text(json.dumps({
                'settings': {'repetitions': 1},
                'rows': [{'condition': 'resample', 'repetition': 1, 'success': True,
                          'heldout': {'passed': True}, 'live_calls': 2, 'history': []}],
                'pending': {'1:feedback': [], '1:counterfactual': []}}))
            report = research_report.generate(root, root / 'out', manifest)
            self.assertEqual(report['scope']['completed'], 1)
            self.assertEqual(report['scope']['pending'], 2)
            self.assertEqual(report['strategies']['resample']['combined_pass'], 1)
            self.assertEqual(report['paired']['resample_vs_feedback']['eligible'], 0)
            self.assertTrue((root / 'out' / 'evaluation-coverage.svg').exists())

    def test_legacy_provider_failure_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'manifest.json').write_text(json.dumps({'tasks': [{'id': 'demo', 'category': 'feature'}]}))
            (root / 'demo-live.json').write_text(json.dumps({
                'rows': [{'condition': 'feedback', 'success': False, 'heldout': {'passed': False},
                          'history': [{'failure_stage': 'model_request', 'failure_category': 'provider_error'}]}],
                'pending': {}}))
            report = research_report.generate(root, root / 'out', root / 'manifest.json')
            self.assertEqual(report['strategies']['feedback']['completed'], 0)
            self.assertEqual(report['strategies']['feedback']['blocked_legacy'], 1)


if __name__ == '__main__':
    unittest.main()
