"""Multi-file transactional adversarial verifier tests; no provider calls."""
import unittest
from benchmarks.v18 import multifile_adversarial as benchmark

class MultiFileAdversarialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = benchmark.run()

    def test_reference_solution_passes_both_suites(self):
        self.assertEqual(self.report['baseline'], {'public_pass': True, 'heldout_pass': True})

    def test_all_three_mutants_pass_public_suite(self):
        self.assertEqual(len(self.report['mutants']), 3)
        for row in self.report['mutants']:
            with self.subTest(mutation=row['mutation']):
                self.assertTrue(row['public_pass'])

    def test_all_three_mutants_fail_heldout_suite(self):
        for row in self.report['mutants']:
            with self.subTest(mutation=row['mutation']):
                self.assertFalse(row['heldout_pass'])

    def test_report_makes_no_agent_success_claim(self):
        self.assertFalse(self.report['agent_evaluated'])
        self.assertEqual(self.report['kind'], 'offline_verifier_sensitivity')

if __name__ == '__main__':
    unittest.main()
