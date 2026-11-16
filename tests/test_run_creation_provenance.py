import unittest
from unittest.mock import patch

from backend import app as backend


class RunCreationProvenanceTests(unittest.TestCase):

    def test_create_run_records_autonomous_provenance(self):
        original_runs = dict(backend.RUNS)

        try:
            backend.RUNS.clear()

            request = backend.RunRequest(
                repository=".",
                task="Test provenance recording",
                strategy="dependency",
                attempts=1,
                max_files=2,
                generate_tests=False,
            )

            with patch.object(
                backend,
                "safe_repo",
                return_value=backend.ROOT,
            ), patch.object(backend.threading, "Thread") as thread:
                response = backend.create_run(request)

            run_id = response["id"]

            self.assertEqual(response["status"], "running")
            self.assertIn(run_id, backend.RUNS)

            run = backend.RUNS[run_id]

            self.assertEqual(
                run["execution_provenance"],
                {
                    "source": "codepilot_agent",
                    "execution_mode": "autonomous",
                    "recorded_at_creation": True,
                },
            )

            thread.assert_called_once()
            thread.return_value.start.assert_called_once()

        finally:
            backend.RUNS.clear()
            backend.RUNS.update(original_runs)


if __name__ == "__main__":
    unittest.main()
