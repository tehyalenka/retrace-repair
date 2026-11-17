"""Unit tests for statistical analysis and experiment manifest tools."""
import json
import tempfile
import unittest
from pathlib import Path

from benchmarks.v18.statistical_analysis import bootstrap_ci, mcnemar_exact_p_value
from benchmarks.v18.experiment_manifest import generate_manifest


class StatisticalAnalysisTests(unittest.TestCase):

    def test_bootstrap_ci_basic_properties(self):
        vals = [1.0] * 10
        mean, low, high = bootstrap_ci(vals)
        self.assertEqual(mean, 1.0)
        self.assertEqual(low, 1.0)
        self.assertEqual(high, 1.0)

    def test_bootstrap_ci_variance(self):
        vals = [0.0] * 10 + [1.0] * 10
        mean, low, high = bootstrap_ci(vals)
        self.assertEqual(mean, 0.5)
        self.assertLess(low, 0.5)
        self.assertGreater(high, 0.5)

    def test_mcnemar_exact_p_value_symmetric(self):
        # When discordance is balanced, p-value should be 1.0
        self.assertEqual(mcnemar_exact_p_value(5, 5), 1.0)

    def test_mcnemar_exact_p_value_zero_discordance(self):
        self.assertEqual(mcnemar_exact_p_value(0, 0), 1.0)

    def test_mcnemar_exact_p_value_extreme(self):
        # 10 successes in A vs 0 in B
        p_val = mcnemar_exact_p_value(10, 0)
        self.assertLess(p_val, 0.01)

    def test_experiment_manifest_generation(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "manifest.json"
            data = generate_manifest(str(out))
            self.assertTrue(out.exists())
            self.assertEqual(data["manifest_schema"], 1)
            self.assertIn("git_commit_sha", data)
            self.assertEqual(data["benchmark_metadata"]["total_tasks"], 22)


if __name__ == "__main__":
    unittest.main()
