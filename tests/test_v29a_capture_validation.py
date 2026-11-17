import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from benchmarks.v18 import task_suite_runner as runner


class CaptureValidationTests(unittest.TestCase):

    def test_zero_discovered_tests_rejected_before_evaluation(self):
        item = {
            "id": "example",
            "category": "bugfix",
            "repo": "unused",
            "public_verifier": "public.py",
            "heldout_verifier": "heldout.py",
            "task": "example task",
        }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "public.py").write_text("public verifier")
            (root / "heldout.py").write_text("heldout verifier")

            with patch.object(runner, "ROOT", root), \
                 patch.object(runner, "tasks", return_value=[item]), \
                 patch.object(runner, "fixture", return_value=root), \
                 patch.object(runner.record_replay, "capture", return_value={
                     "first_attempt": {
                         "failure_category": "test_failure",
                         "failure_stage": "smoke_tests",
                         "tests_run": 0,
                         "output": "No tests discovered",
                     }
                 }), \
                 patch.object(
                     runner.checkpointed_three_arm, "evaluate"
                 ) as evaluate:

                with self.assertRaisesRegex(
                    ValueError, "genuine public-test failure"
                ):
                    runner.run_live(root / "results")

                evaluate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
