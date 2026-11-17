import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from benchmarks.v18 import task_suite_runner as runner


class SuiteBudgetTests(unittest.TestCase):

    def test_budget_forwarded_to_checkpoint_engine(self):
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
                     "first_attempt": {"failure_category": "test_failure"}
                 }), \
                 patch.object(runner.checkpointed_three_arm, "evaluate",
                              return_value={"rows": []}) as evaluate:

                runner.run_live(
                    root / "results",
                    repetitions=2,
                    attempts=3,
                    max_http_requests_per_arm=6,
                )

                self.assertEqual(
                    evaluate.call_args.kwargs["max_http_requests_per_arm"],
                    6,
                )

    def test_budget_exhaustion_preserves_controlled_stop(self):
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
                     "first_attempt": {"failure_category": "test_failure"}
                 }), \
                 patch.object(
                     runner.checkpointed_three_arm,
                     "evaluate",
                     side_effect=runner.checkpointed_three_arm.BenchmarkBudgetExceeded(
                         "budget exhausted"
                     ),
                 ), \
                 patch.object(runner, "summarize") as summarize:

                result = runner.run_live(
                    root / "results",
                    max_http_requests_per_arm=6,
                )

                self.assertEqual(result, [])
                summarize.assert_called_once()


if __name__ == "__main__":
    unittest.main()
