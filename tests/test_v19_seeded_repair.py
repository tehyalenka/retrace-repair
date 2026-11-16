import unittest
from benchmarks.v19.seeded_repair import run_case, safe_feedback

class SeededRepairTests(unittest.TestCase):
    def test_offline_all_cases(self):
        for case in ("bugfix", "feature", "refactor"):
            with self.subTest(case=case):
                result = run_case(case, offline=True)
                self.assertTrue(result["same_initial_defect"])
                for row in result["rows"]:
                    self.assertTrue(row["success"])
                    self.assertEqual(row["fresh_model_calls"], 0)
                    self.assertEqual(row["history"][0]["failure_category"], "test_failure")
                    self.assertEqual(row["model_calls"][0]["origin"], "seeded_defect")
                    self.assertEqual(row["model_calls"][1]["origin"], "scripted_correction")
                self.assertFalse(result["rows"][0]["model_calls"][1]["feedback_message_present"])
                self.assertTrue(result["rows"][1]["model_calls"][1]["feedback_message_present"])

    def test_feedback_does_not_expose_assertions(self):
        text = safe_feedback({"failure_stage": "independent_verification", "failure_category": "test_failure",
                              "verification_output": "test_case (Verify) ... FAIL\nTraceback\n    self.assertEqual(secret, 123)"})
        self.assertIn("test_case", text)
        self.assertNotIn("assertEqual", text)
        self.assertNotIn("secret", text)
