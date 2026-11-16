import tempfile
import unittest
from pathlib import Path

from codepilot.repository_analyzer import (
    index_repository,
    rank_context_files,
)


class RetrievalRecallTests(unittest.TestCase):

    def test_symbol_aware_recall_at_four(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)

            files = {
                "orders.py": (
                    "class OrderService:\n"
                    "    def __init__(self, inventory: Inventory, "
                    "pricing: Pricing, payments: Payments):\n"
                    "        pass\n"
                ),
                "inventory.py": "class Inventory:\n    pass\n",
                "pricing.py": "class Pricing:\n    pass\n",
                "payments.py": "class Payments:\n    pass\n",
                "aaa_unrelated.py": "class UnrelatedA:\n    pass\n",
                "aab_unrelated.py": "class UnrelatedB:\n    pass\n",
                "aac_unrelated.py": "class UnrelatedC:\n    pass\n",
            }

            for name, content in files.items():
                (repo / name).write_text(content)

            entries = index_repository(repo)
            task = "Implement OrderService"

            lexical = rank_context_files(
                entries, task,
                strategy="lexical",
                repo_path=repo,
            )
            dependency = rank_context_files(
                entries, task,
                strategy="dependency",
                repo_path=repo,
            )

            relevant = {
                "orders.py",
                "inventory.py",
                "pricing.py",
                "payments.py",
            }

            lexical_recall = len(
                set(lexical[:4]) & relevant
            ) / len(relevant)

            dependency_recall = len(
                set(dependency[:4]) & relevant
            ) / len(relevant)

            print("\nLexical Recall@4:", lexical_recall)
            print("Dependency Recall@4:", dependency_recall)

            self.assertEqual(lexical_recall, 0.25)
            self.assertEqual(dependency_recall, 1.0)
            self.assertGreater(
                dependency_recall,
                lexical_recall,
            )


if __name__ == "__main__":
    unittest.main()
