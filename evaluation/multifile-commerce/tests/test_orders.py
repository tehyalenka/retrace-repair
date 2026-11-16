import unittest

from inventory import STOCK
from orders import create_order


class OrderTests(unittest.TestCase):

    def setUp(self):
        STOCK.clear()
        STOCK.update({
            "laptop": 5,
            "mouse": 10,
            "keyboard": 8,
        })

    def test_successful_order(self):
        result = create_order("mouse", 2)

        self.assertEqual(result["product"], "mouse")
        self.assertEqual(result["quantity"], 2)
        self.assertEqual(result["total"], 2000)
        self.assertEqual(STOCK["mouse"], 8)

    def test_insufficient_stock(self):
        with self.assertRaises(ValueError):
            create_order("laptop", 10)

        self.assertEqual(STOCK["laptop"], 5)


if __name__ == "__main__":
    unittest.main()
