import unittest
from engine import generate_report
from renderer import render_report
from formatter import format_record

class IndependentReportTests(unittest.TestCase):
    def test_new_optional_prefix(self):
        self.assertEqual(generate_report([{'name':'A','score':2}], prefix='> '), '> A:2')
    def test_default_backward_compat(self):
        self.assertEqual(generate_report([{'name':'A','score':2}]), 'A:2')
    def test_multiple(self):
        self.assertEqual(generate_report([{'name':'A','score':2},{'name':'B','score':3}], prefix='* '), '* A:2\n* B:3')
    def test_empty(self):
        self.assertEqual(generate_report([], prefix='* '), '')
    def test_existing_renderer(self):
        self.assertEqual(render_report([{'name':'A','score':2}]), 'A:2')
    def test_existing_formatter(self):
        self.assertEqual(format_record({'name':'A','score':2}), 'A:2')
