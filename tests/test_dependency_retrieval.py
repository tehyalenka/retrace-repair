import tempfile
import unittest
from pathlib import Path
from codepilot.repository_analyzer import (index_repository, dependency_graph,
    rank_context_files, retrieve_context)


class DependencyRetrievalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        (self.repo / "booking.py").write_text("from ledger import debit\ndef cancel_booking():\n    return debit()\n")
        (self.repo / "ledger.py").write_text("def debit():\n    return 1\n")
        (self.repo / "unrelated.py").write_text("def unrelated():\n    pass\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_local_import_graph(self):
        graph = dependency_graph(index_repository(self.repo))
        self.assertEqual(graph["booking.py"], ["ledger.py"])
        self.assertEqual(graph["ledger.py"], [])

    def test_dependency_promotes_neighbor(self):
        entries = index_repository(self.repo)
        self.assertEqual(rank_context_files(entries, "cancel_booking", "lexical")[1], "ledger.py")
        self.assertEqual(rank_context_files(entries, "cancel_booking", "dependency")[:2],
                         ["booking.py", "ledger.py"])

    def test_context_budget_and_mode(self):
        result = retrieve_context(self.repo, "cancel_booking", max_files=2,
                                  max_chars=150, strategy="dependency")
        self.assertIn("### booking.py", result)
        self.assertIn("### ledger.py", result)
        self.assertNotIn("unrelated.py", result)

    def test_invalid_strategy(self):
        with self.assertRaises(ValueError):
            retrieve_context(self.repo, "cancel_booking", strategy="random")


if __name__ == "__main__":
    unittest.main()
