import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from benchmarks.v18 import leakage_resistant as lr
from benchmarks.v18 import checkpointed_three_arm as cp

HERE = Path(__file__).resolve().parents[1] / "benchmarks" / "v18" / "verifiers"
PUBLIC = HERE / "double_public.py"
HIDDEN = HERE / "double_heldout.py"


class LeakageResistantTests(unittest.TestCase):
    def test_public_capture_and_heldout_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace, output = Path(tmp) / "trace.json", Path(tmp) / "report.json"
            lr.capture("offline", "bugfix", trace, PUBLIC, HIDDEN)
            report = lr.evaluate(trace, output, PUBLIC, HIDDEN, offline=True)
            self.assertEqual(len(report["rows"]), 3)
            self.assertTrue(all(r["heldout"]["passed"] for r in report["rows"]))
            self.assertTrue(all(r["heldout"]["tests_run"] == 3 for r in report["rows"]))
            self.assertTrue(all("test_negative" not in json.dumps(r["calls"]) for r in report["rows"]))
            self.assertEqual(len(lr.evaluate(trace, output, PUBLIC, HIDDEN, offline=True)["rows"]), 3)

    def test_wrong_public_verifier_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = Path(tmp) / "trace.json"
            lr.capture("offline", "bugfix", trace, PUBLIC, HIDDEN)
            with self.assertRaises(ValueError):
                lr.evaluate(trace, Path(tmp) / "report.json", HIDDEN, PUBLIC, offline=True)

    def test_heldout_change_invalidates_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace, output = Path(tmp) / "trace.json", Path(tmp) / "report.json"
            lr.capture("offline", "bugfix", trace, PUBLIC, HIDDEN)
            lr.evaluate(trace, output, PUBLIC, HIDDEN, offline=True)
            modified = Path(tmp) / "different.py"
            modified.write_text(HIDDEN.read_text() + "\n# changed\n")
            with self.assertRaises(ValueError):
                lr.evaluate(trace, output, PUBLIC, modified, offline=True)

    def test_heldout_failure_not_used_as_feedback(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace, output = Path(tmp) / "trace.json", Path(tmp) / "report.json"
            lr.capture("offline", "bugfix", trace, PUBLIC, HIDDEN)
            with patch.object(cp, "_heldout_check", return_value={"passed": False, "tests_run": 1, "output": "heldout fail"}):
                report = lr.evaluate(trace, output, PUBLIC, HIDDEN, offline=True)
            self.assertTrue(all(r["success"] and not r["heldout"]["passed"] for r in report["rows"]))
            self.assertTrue(all("heldout fail" not in json.dumps(r["calls"]) for r in report["rows"]))
