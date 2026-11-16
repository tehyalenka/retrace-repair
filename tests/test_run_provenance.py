import json
import tempfile
import unittest
from pathlib import Path

from backend.run_artifacts import save_run_artifacts


class RunProvenanceTests(unittest.TestCase):

    def test_provenance_survives_artifact_persistence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "sample-repo"
            repo.mkdir()
            (repo / "example.py").write_text("value = 1\n")

            run_id = "123456abcdef"

            run = {
                "id": run_id,
                "repository": "sample-repo",
                "task": "Update example",
                "status": "completed",
                "started_at": "2026-11-16T10:00:00+00:00",
                "finished_at": "2026-11-16T10:01:00+00:00",
                "execution_provenance": {
                    "source": "codepilot_agent",
                    "execution_mode": "autonomous",
                    "recorded_at_creation": True,
                },
                "result": {
                    "success": True,
                    "history": [{
                        "attempt": 1,
                        "passed": True,
                        "changed_files": ["example.py"],
                        "tests_run": 1,
                    }],
                    "files": {
                        "example.py": "value = 2\n",
                    },
                },
            }

            save_run_artifacts(root, run)

            metadata = (
                root / ".codepilot-runs" / run_id / "run.json"
            )

            self.assertTrue(metadata.exists())

            saved = json.loads(metadata.read_text())

            self.assertEqual(
                saved["execution_provenance"]["source"],
                "codepilot_agent",
            )
            self.assertEqual(
                saved["execution_provenance"]["execution_mode"],
                "autonomous",
            )
            self.assertTrue(
                saved["execution_provenance"]["recorded_at_creation"]
            )


if __name__ == "__main__":
    unittest.main()
