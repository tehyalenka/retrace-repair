"""Offline tests for the repeated benchmark aggregator."""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class RepeatBenchmarkTests(unittest.TestCase):
    def _v09_folder(self):
        root = Path(__file__).resolve().parents[1]
        archived = root / "benchmarks" / "archive" / "v09"
        return archived if archived.exists() else (root / "benchmarks" / "v09")

    def test_repeat_summary_and_failure_handling(self):
        folder = self._v09_folder()
        sys.path.insert(0, str(folder))
        try:
            spec = importlib.util.spec_from_file_location("codepilot_repeat", folder / "repeat.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            calls = []

            def fake_evaluate(names, attempts, generated, output):
                calls.append((names, attempts, generated))
                cases = []
                for name in names:
                    passed = attempts == 3 or name != "bugfix"
                    cases.append({"case": name, "success": passed,
                                  "first_attempt_passed": name != "bugfix",
                                  "attempts_used": 2 if attempts == 3 and name == "bugfix" else 1,
                                  "elapsed_seconds": 2.0, "history": []})
                Path(output).write_text(json.dumps({"cases": cases}))
                return {"cases": cases}

            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "summary.json"
                result = module.run_repeated(2, [1, 3], path, evaluator=fake_evaluate)
                self.assertEqual(len(calls), 4)
                self.assertEqual(len(result["runs"]), 12)
                self.assertAlmostEqual(result["summary"][0]["success_rate"], 2 / 3)
                self.assertEqual(result["summary"][1]["success_rate"], 1.0)
                self.assertEqual(result["summary"][1]["recovered_after_failure"], 2)
                self.assertEqual(json.loads(path.read_text()), result)
                self.assertEqual(len(list(Path(tmp).glob("summary-attempts*-run*.json"))), 4)
        finally:
            sys.path.remove(str(folder))

    def test_reject_invalid_settings(self):
        folder = self._v09_folder()
        sys.path.insert(0, str(folder))
        try:
            spec = importlib.util.spec_from_file_location("codepilot_repeat_invalid", folder / "repeat.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            with self.assertRaises(ValueError):
                module.run_repeated(0, [1], "unused.json")
            with self.assertRaises(ValueError):
                module.run_repeated(1, [0], "unused.json")
        finally:
            sys.path.remove(str(folder))


if __name__ == "__main__":
    unittest.main()
