"""Offline regression checks for the controlled v1.5 benchmark."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

root = Path(__file__).resolve().parents[1]
archived_path = root / "benchmarks" / "archive" / "v15" / "evaluate.py"
MODULE = archived_path if archived_path.exists() else (root / "benchmarks" / "v15" / "evaluate.py")
spec = importlib.util.spec_from_file_location("v15_evaluate", MODULE)
v15 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v15)


class V15RetrievalTests(unittest.TestCase):
    def test_fixture_contains_twelve_distractors_and_import(self):
        with tempfile.TemporaryDirectory() as temp:
            gold = v15.make_fixture(temp, v15.SCENARIOS[0])
            self.assertEqual(len(list(Path(temp).glob("*.py"))), 14)
            self.assertEqual(gold, {"checkout.py", "ledger.py"})
            self.assertIn("import ledger", (Path(temp) / "checkout.py").read_text())

    def test_metrics_are_set_based(self):
        self.assertEqual(v15.metrics(["a.py", "b.py"], {"a.py", "c.py"})["recall"], 0.5)

    def test_strategies_diverge_at_tight_budget(self):
        report = v15.evaluate(max_files=2)
        self.assertEqual(len(report["results"]), 8)
        self.assertGreater(report["summary"]["dependency"]["recall"],
                           report["summary"]["lexical"]["recall"])

    def test_reproducible(self):
        self.assertEqual(v15.evaluate(max_files=2), v15.evaluate(max_files=2))

    def test_output_is_valid_json(self):
        import json
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "results.json"
            report = v15.evaluate(output=target)
            self.assertEqual(json.loads(target.read_text()), report)

    def test_invalid_arguments(self):
        with self.assertRaises(ValueError):
            v15.evaluate(max_files=0)
