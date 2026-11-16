"""Offline regression tests for a narrowly recoverable JSON edit boundary."""
import json
import unittest
from unittest.mock import patch
from codepilot.agent import parse_edits, parse_edits_with_format_retry


class V29JSONRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.good = json.dumps({"reasoning_summary": "two edits", "edits": [
            {"path": "catalog.py", "operation": "modify", "content": 'print("x")\n'},
            {"path": "orders.py", "operation": "modify", "content": "value = 2\n"},
        ]}, separators=(',', ':'))
        self.bad = self.good.replace('},{"path":"orders.py"', '},"{"path":"orders.py"')
        self.assertNotEqual(self.good, self.bad)

    def test_observed_boundary_recovers_without_provider(self):
        metrics = {}
        with patch('codepilot.agent.ask_model') as provider:
            result = parse_edits_with_format_retry([], self.bad, diagnostics=metrics)
        provider.assert_not_called()
        self.assertEqual([e['path'] for e in result['edits']], ['catalog.py', 'orders.py'])
        self.assertEqual(result['edits'][0]['content'], 'print("x")\n')
        self.assertEqual(metrics['format_retries_used'], 0)

    def test_valid_json_unchanged(self):
        result = parse_edits(self.good)
        self.assertEqual(result['edits'][1]['content'], 'value = 2\n')

    def test_ambiguous_multiple_boundaries_rejected(self):
        third = {"path": "extra.py", "operation": "modify", "content": "pass\n"}
        valid = json.dumps({"edits": [
            {"path": "a.py", "content": "a"},
            {"path": "b.py", "content": "b"}, third]}, separators=(',', ':'))
        invalid = valid.replace('},{"path"', '},"{"path"')
        with self.assertRaises(json.JSONDecodeError):
            parse_edits(invalid)

    def test_schema_still_rejects_invalid_edit(self):
        invalid = self.bad.replace('"operation":"modify"', '"operation":"execute"', 1)
        with self.assertRaises(ValueError):
            parse_edits(invalid)

    def test_unrelated_malformed_json_rejected(self):
        with self.assertRaises(json.JSONDecodeError):
            parse_edits('{broken')


if __name__ == '__main__':
    unittest.main()
