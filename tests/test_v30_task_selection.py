import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from benchmarks.v18 import task_suite_runner as runner


class TaskSelectionTests(unittest.TestCase):

    def test_single_task_only_evaluates_selected_fixture(self):
        selected = "clamp_bounds"
        visited = []

        class StopAfterSelection(Exception):
            pass

        def fake_fixture(item, repo_dir):
            visited.append(item["id"])
            raise StopAfterSelection()

        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(runner, "fixture", side_effect=fake_fixture):
                with self.assertRaises(StopAfterSelection):
                    runner.run_live(
                        Path(tmp),
                        task_id=selected,
                    )

        self.assertEqual(visited, [selected])

    def test_unknown_task_is_not_in_manifest(self):
        ids = {item["id"] for item in runner.tasks()}
        self.assertIn("clamp_bounds", ids)
        self.assertNotIn("nonexistent_task", ids)


if __name__ == "__main__":
    unittest.main()
