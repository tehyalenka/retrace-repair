import json
import tempfile
import unittest
from pathlib import Path

from benchmarks.v18 import research_report


class CheckpointReportingTests(unittest.TestCase):

    def test_checkpoint_reservations_and_tokens(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            manifest = {
                "tasks": [
                    {"id": "example", "category": "bugfix"}
                ]
            }

            (root / "manifest.json").write_text(
                json.dumps(manifest),
                encoding="utf-8",
            )

            checkpoint = {
                "settings": {"repetitions": 1},
                "request_reservations": {
                    "1:resample": 3,
                    "1:feedback": 2,
                },
                "rows": [
                    {
                        "key": "1:resample",
                        "condition": "resample",
                        "repetition": 1,
                        "success": True,
                        "heldout": {"passed": True},
                        "live_calls": 1,
                        "request_accounting": {
                            "http_requests": 3,
                            "prompt_tokens": 120,
                            "completion_tokens": 40,
                            "usage_reports": 1,
                        },
                    }
                ],
                "pending": {
                    "1:feedback": {}
                },
            }

            (root / "example-live.json").write_text(
                json.dumps(checkpoint),
                encoding="utf-8",
            )

            records = research_report.collect(
                root,
                root / "manifest.json",
            )

            by_arm = {r["arm"]: r for r in records}

            self.assertEqual(
                by_arm["resample"]["http_requests"], 3
            )
            self.assertEqual(
                by_arm["resample"]["prompt_tokens"], 120
            )
            self.assertEqual(
                by_arm["resample"]["completion_tokens"], 40
            )
            self.assertEqual(
                by_arm["feedback"]["http_requests"], 2
            )
            self.assertEqual(
                by_arm["feedback"]["status"], "pending"
            )
            self.assertIsNone(
                by_arm["counterfactual"].get("http_requests")
            )

            summary = research_report.summarize(records)

            self.assertEqual(
                summary["resource_usage"]["resample"]
                ["known_http_requests"],
                3,
            )
            self.assertEqual(
                summary["resource_usage"]["feedback"]
                ["known_http_requests"],
                2,
            )
            self.assertEqual(
                summary["resource_usage"]["resample"]
                ["observed_prompt_tokens"],
                120,
            )


if __name__ == "__main__":
    unittest.main()
