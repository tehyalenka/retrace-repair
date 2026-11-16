import tempfile
import unittest
from pathlib import Path
from benchmarks.v18.record_replay import capture, paired


class PairedCounterfactualTests(unittest.TestCase):
    def test_three_arms_share_initial_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            trace = Path(temp) / "capture.json"
            output = Path(temp) / "paired.json"
            capture("offline", "bugfix", trace)
            result = paired(trace, output, offline=True, include_counterfactual=True)
            self.assertEqual([r["condition"] for r in result["rows"]],
                             ["resample", "feedback", "counterfactual"])
            first = [r["model_calls"][0]["response"] for r in result["rows"]]
            self.assertEqual(len(set(first)), 1)
            self.assertTrue(all(r["history"][0]["failure_category"] == "test_failure"
                                for r in result["rows"]))
            self.assertEqual(result["rows"][2]["repair_policy"], "counterfactual")
            self.assertTrue(all(r["fresh_model_calls"] == 0 for r in result["rows"]))
            self.assertTrue(output.is_file())


if __name__ == "__main__":
    unittest.main()
