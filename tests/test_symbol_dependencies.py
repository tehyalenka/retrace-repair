import tempfile
import unittest
from pathlib import Path

from codepilot.repository_analyzer import (
    dependency_graph,
    index_repository,
)


class SymbolDependencyTests(unittest.TestCase):

    def test_typed_constructor_dependencies(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)

            files = {
                "inventory.py": "class Inventory:\n    pass\n",
                "pricing.py": "class Pricing:\n    pass\n",
                "payments.py": "class Payments:\n    pass\n",
                "orders.py": (
                    "class OrderService:\n"
                    "    def __init__(self, inventory: Inventory, "
                    "pricing: Pricing, payments: Payments):\n"
                    "        self.inventory = inventory\n"
                ),
            }

            for name, content in files.items():
                (repo / name).write_text(content)

            graph = dependency_graph(index_repository(repo), repo_path=repo)

            self.assertEqual(
                set(graph["orders.py"]),
                {"inventory.py", "pricing.py", "payments.py"},
            )


if __name__ == "__main__":
    unittest.main()
