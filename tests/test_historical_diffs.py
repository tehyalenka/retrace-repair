import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from backend import app as app_module
    from backend.run_artifacts import save_run_artifacts
    HAS_BACKEND = True
except ImportError:
    HAS_BACKEND = False
    app_module = None
    save_run_artifacts = None


@unittest.skipUnless(HAS_BACKEND, "Backend dependencies not installed")
class HistoricalDiffTests(unittest.TestCase):

    def test_diff_remains_stable_after_repository_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "sample"
            repo.mkdir()

            source = repo / "example.py"
            source.write_text("value = 1\n", encoding="utf-8")

            run = {
                "id": "123456abcdef",
                "repository": "sample",
                "task": "Historical diff regression",
                "status": "completed",
                "started_at": "2026-11-16T00:00:00+00:00",
                "finished_at": "2026-11-16T00:00:01+00:00",
                "result": {
                    "success": True,
                    "files": {"example.py": "value = 2\n"},
                },
            }

            save_run_artifacts(root, run)

            with patch.object(app_module, "ROOT", root), \
                 patch.object(app_module, "safe_repo", return_value=repo), \
                 patch.object(
                     app_module,
                     "load_saved_runs",
                     return_value={run["id"]: run},
                 ), \
                 patch.dict(app_module.RUNS, {}, clear=True):

                first = app_module.run_diff(run["id"])["diffs"]["example.py"]

                source.write_text("value = 999\n", encoding="utf-8")

                second = app_module.run_diff(run["id"])["diffs"]["example.py"]

            self.assertEqual(first, second)
            self.assertIn("-value = 1", first)
            self.assertIn("+value = 2", first)
            self.assertNotIn("999", second)


if __name__ == "__main__":
    unittest.main()
