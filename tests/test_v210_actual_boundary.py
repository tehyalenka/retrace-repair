import json
import unittest
from codepilot.agent import parse_edits

class V210BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.valid = json.dumps({'edits': [
            {'path': 'catalog.py', 'operation': 'modify', 'content': 'return total\n'},
            {'path': 'orders.py', 'operation': 'modify', 'content': 'return {"total": total}\n'},
        ]}, separators=(',', ':'))

    def test_actual_separator_shape(self):
        malformed = self.valid.replace('},{"path":"orders.py"', '},"{"path":"orders.py"')
        self.assertEqual([e['path'] for e in parse_edits(malformed)['edits']], ['catalog.py', 'orders.py'])

    def test_valid_unchanged(self):
        self.assertEqual(parse_edits(self.valid), json.loads(self.valid))

    def test_multiple_ambiguous_rejected(self):
        valid = json.dumps({'edits': [
            {'path': 'a.py', 'content': 'x'}, {'path': 'b.py', 'content': 'y'}, {'path': 'c.py', 'content': 'z'}
        ]}, separators=(',', ':'))
        bad = valid.replace('},{"path"', '},"{"path"')
        with self.assertRaises(json.JSONDecodeError):
            parse_edits(bad)

    def test_unrelated_invalid_rejected(self):
        with self.assertRaises(json.JSONDecodeError):
            parse_edits('{broken')

if __name__ == '__main__':
    unittest.main()
