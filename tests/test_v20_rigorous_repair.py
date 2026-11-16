import unittest
from benchmarks.v19.seeded_repair import SEEDS, run_case
from benchmarks.v20.rigorous_repair import evaluate

class V20Tests(unittest.TestCase):
    def test_no_defect_hints(self):
        for path, source in SEEDS.values():
            self.assertNotIn('# Defect:', source)

    def test_reversed_order(self):
        result = run_case('feature', offline=True, condition_order=('feedback', 'resample'))
        self.assertEqual([r['condition'] for r in result['rows']], ['feedback', 'resample'])
        self.assertTrue(all(r['success'] for r in result['rows']))

    def test_repeated_summary(self):
        result = evaluate(mode='offline', cases=['bugfix'], repeats=2)
        self.assertFalse(result['errors'])
        for arm in ('resample', 'feedback'):
            self.assertEqual(result['summary'][arm]['trials'], 2)
            self.assertEqual(result['summary'][arm]['successful_repairs'], 2)
            self.assertEqual(result['summary'][arm]['fresh_model_calls'], 0)
