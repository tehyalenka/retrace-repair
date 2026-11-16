import unittest

from inventory import STOCK, reserve
from pricing import calculate_total
from orders import create_order


class IndependentOrderTests(unittest.TestCase):

    def setUp(self):
        STOCK.clear()
        STOCK.update({
            "laptop": 5,
            "mouse": 10,
            "keyboard": 8,
        })

    def test_zero_quantity(self):
        with self.assertRaises(ValueError):
            create_order("mouse", 0)

    def test_negative_quantity(self):
        with self.assertRaises(ValueError):
            create_order("mouse", -2)

    def test_boolean_quantity(self):
        with self.assertRaises(ValueError):
            create_order("mouse", True)

    def test_unknown_product(self):
        with self.assertRaises(ValueError):
            create_order("unknown", 1)

    def test_exact_stock(self):
        result = create_order("laptop", 5)
        self.assertEqual(result["total"], 250000)
        self.assertEqual(STOCK["laptop"], 0)

    def test_reservation(self):
        reserve("keyboard", 3)
        self.assertEqual(STOCK["keyboard"], 5)

    def test_pricing(self):
        self.assertEqual(calculate_total("keyboard", 3), 6000)

    def test_no_stock_loss_on_invalid_order(self):
        with self.assertRaises(ValueError):
            create_order("mouse", -1)

        self.assertEqual(STOCK["mouse"], 10)


if __name__ == "__main__":
    unittest.main()
