import tempfile
import unittest
from pathlib import Path

from codepilot.repository_analyzer import (
    discover_python_files,
    retrieve_context,
)


class RetrievalFilteringTests(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)

        files = {
            "inventory.py": (
                "class Inventory:\n"
                "    def reserve(self, items):\n"
                "        return True\n"
            ),
            "orders.py": (
                "from inventory import Inventory\n"
                "class OrderService:\n"
                "    pass\n"
            ),
            "payments.py": (
                "class Payments:\n"
                "    pass\n"
            ),
            "tests/__init__.py": "",
            "tests/test_inventory.py": (
                "import unittest\n"
                "from inventory import Inventory\n"
                "class InventoryTests(unittest.TestCase):\n"
                "    def test_reserve(self):\n"
                "        self.assertTrue(Inventory().reserve([]))\n"
            ),
        }

        for name, content in files.items():
            path = self.repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)

    def tearDown(self):
        self.temp.cleanup()

    def selected_files(self, task, strategy="lexical", max_files=5):
        context = retrieve_context(
            self.repo,
            task,
            max_files=max_files,
            strategy=strategy,
        )

        return [
            line[4:]
            for line in context.splitlines()
            if line.startswith("### ")
        ]

    def test_normal_task_excludes_tests(self):
        for strategy in ("lexical", "dependency"):
            with self.subTest(strategy=strategy):
                files = self.selected_files(
                    "Fix Inventory.reserve",
                    strategy,
                )

                self.assertIn("inventory.py", files)
                self.assertNotIn("tests/__init__.py", files)
                self.assertNotIn("tests/test_inventory.py", files)

    def test_explicit_test_task_includes_tests(self):
        for strategy in ("lexical", "dependency"):
            with self.subTest(strategy=strategy):
                files = self.selected_files(
                    "Add tests for Inventory.reserve",
                    strategy,
                )

                self.assertIn("tests/test_inventory.py", files)

    def test_context_budget_excludes_tests(self):
        for strategy in ("lexical", "dependency"):
            with self.subTest(strategy=strategy):
                files = self.selected_files(
                    "Fix Inventory.reserve",
                    strategy,
                    max_files=2,
                )

                self.assertEqual(len(files), 2)
                self.assertTrue(
                    all(not path.startswith("tests/") for path in files)
                )

    def test_test_files_remain_discoverable(self):
        files = discover_python_files(self.repo)

        self.assertIn("tests/__init__.py", files)
        self.assertIn("tests/test_inventory.py", files)


if __name__ == "__main__":
    unittest.main()
