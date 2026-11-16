import tempfile
import unittest
from pathlib import Path
from benchmarks.v16.repair_experiment import run

class RepairExperimentTests(unittest.TestCase):
    def test_scripted_comparison(self):
        with tempfile.TemporaryDirectory() as d:
            report = run("offline", runs=1, output=str(Path(d)/"out.json"))
            self.assertEqual(report["summary"]["single"]["successes"], 0)
            self.assertEqual(report["summary"]["feedback"]["successes"], 1)
            self.assertEqual(report["summary"]["resample"]["successes"], 1)
            self.assertEqual(report["summary"]["feedback"]["recovered_code_failures"], 1)
            self.assertEqual(report["summary"]["feedback"]["infrastructure_failures"], 0)
    def test_reject_invalid_arguments(self):
        with self.assertRaises(ValueError): run("offline", runs=0)
        with self.assertRaises(ValueError): run("offline", cooldown=-1)
