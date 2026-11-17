import unittest
from engine import generate_report

class ReportSmoke(unittest.TestCase):
    def test_single(self):
        self.assertEqual(generate_report([{'name': 'A', 'score': 1}]), 'A:1')
