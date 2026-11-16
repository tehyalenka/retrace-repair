import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from benchmarks.v18.record_replay import capture, paired


class RecordReplayTests(unittest.TestCase):
    def test_offline_capture_and_paired_replay(self):
        with tempfile.TemporaryDirectory() as temp:
            trace = Path(temp) / "trace.json"
            report = Path(temp) / "paired.json"
            first = capture("offline", "bugfix", trace)
            self.assertEqual(first["first_attempt"]["failure_category"], "test_failure")
            self.assertEqual(first["calls"][0]["response"], json.loads(trace.read_text())["calls"][0]["response"])
            result = paired(trace, report, offline=True)
            self.assertTrue(all(r["success"] for r in result["rows"]))
            self.assertEqual([r["condition"] for r in result["rows"]], ["resample", "feedback"])
            self.assertTrue(all(r["fresh_model_calls"] == 0 for r in result["rows"]))
            self.assertTrue(all(r["scripted_continuations"] == 1 for r in result["rows"]))
            self.assertEqual(result["rows"][0]["model_calls"][1]["messages"],
                             result["rows"][0]["model_calls"][0]["messages"])
            self.assertGreater(len(result["rows"][1]["model_calls"][1]["messages"]), 2)

    def test_rejects_successful_initial_edit(self):
        with tempfile.TemporaryDirectory() as temp:
            trace = Path(temp) / "trace.json"
            capture("offline", "bugfix", trace)
            data = json.loads(trace.read_text())
            data["first_attempt"]["failure_category"] = None
            trace.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "test failure"):
                paired(trace, Path(temp) / "out.json", offline=True)

    def test_rejects_mismatched_repo(self):
        with tempfile.TemporaryDirectory() as temp:
            trace = Path(temp) / "trace.json"
            capture("offline", "bugfix", trace)
            data = json.loads(trace.read_text())
            data["repo_sha256"] = "0" * 64
            trace.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "Repository"):
                paired(trace, Path(temp) / "out.json", offline=True)


if __name__ == "__main__":
    unittest.main()
