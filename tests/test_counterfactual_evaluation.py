import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from scripts.evaluate_counterfactual import evaluate, summarize


class CounterfactualEvaluationTests(unittest.TestCase):
    def test_summary_handles_zero_eligible_repairs(self):
        result = summarize([{"arm": "standard", "success": True, "attempts": 1,
                             "initial_failure_category": None, "elapsed_seconds": 1}])
        self.assertIsNone(result["standard"]["repair_recovery_rate"])
        self.assertEqual(result["standard"]["success_rate"], 1)

    def test_three_arms_checkpoint_and_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "repo").mkdir()
            (root / "verifier.py").write_text("# independent verifier\n")
            manifest = {"tasks": [{"id": "one", "repository": str(root / "repo"),
                                    "task": "fix", "verification_file": str(root / "verifier.py")}]}
            def fake_agent(*args, **kwargs):
                return {"success": True, "history": [{"passed": False, "failure_category": "test_failure"},
                                                      {"passed": True}]}
            with patch("scripts.evaluate_counterfactual.run_agent", side_effect=fake_agent) as model:
                result = evaluate(manifest, root / "report.json", repetitions=2)
                self.assertEqual(model.call_count, 6)
                evaluate(manifest, root / "report.json", repetitions=2)
                self.assertEqual(model.call_count, 6)
            self.assertEqual(len(result["results"]), 6)
            self.assertEqual(result["summary"]["counterfactual"]["repair_recovery_rate"], 1)

    def test_resume_rejects_changed_verifier(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "repo").mkdir()
            verifier = root / "verify.py"
            verifier.write_text("a")
            manifest = {"tasks": [{"id": "one", "repository": str(root / "repo"),
                                    "task": "fix", "verification_file": str(verifier)}]}
            with patch("scripts.evaluate_counterfactual.run_agent", return_value={"success": True, "history": [{"passed": True}]}):
                evaluate(manifest, root / "report.json", repetitions=1)
            verifier.write_text("b")
            with self.assertRaisesRegex(ValueError, "different configuration"):
                evaluate(manifest, root / "report.json", repetitions=1)
