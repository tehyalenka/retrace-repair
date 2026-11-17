"""Offline, deterministic multi-file verification challenge; trusted code only.

This tests verifier sensitivity, NOT autonomous agent repair performance.
"""
import json
import tempfile
from pathlib import Path
from benchmarks.v18.task_suite_runner import verify

FILES = {
    'inventory.py': '''stock = {"a": 5, "b": 2}\ndef reserve(items):
    if any(q <= 0 or stock.get(k, 0) < q for k, q in items.items()):
        return False
    for k, q in items.items():
        stock[k] -= q
    return True
''',
    'payments.py': '''def charge(payment_ok):
    return bool(payment_ok)
''',
    'orders.py': '''import inventory
import payments
processed = set()
def purchase(order_id, items, payment_ok=True):
    if order_id in processed:
        return False
    if not inventory.reserve(items):
        return False
    if not payments.charge(payment_ok):
        for k, q in items.items():
            inventory.stock[k] += q
        return False
    processed.add(order_id)
    return True
''',
}

PUBLIC = '''import unittest
import inventory, orders
class Public(unittest.TestCase):
    def test_single_purchase(self):
        self.assertTrue(orders.purchase("first", {"a": 1}))
        self.assertEqual(inventory.stock["a"], 4)
'''

HELDOUT = '''import unittest
import inventory, orders
class Heldout(unittest.TestCase):
    def test_payment_failure_restores_stock(self):
        before = dict(inventory.stock)
        self.assertFalse(orders.purchase("fail", {"a": 2}, False))
        self.assertEqual(inventory.stock, before)
    def test_insufficient_multi_item_is_atomic(self):
        before = dict(inventory.stock)
        self.assertFalse(orders.purchase("insufficient", {"a": 1, "b": 3}))
        self.assertEqual(inventory.stock, before)
    def test_duplicate_idempotency(self):
        self.assertTrue(orders.purchase("dup", {"a": 1}))
        after = dict(inventory.stock)
        self.assertFalse(orders.purchase("dup", {"a": 1}))
        self.assertEqual(inventory.stock, after)
    def test_invalid_quantities(self):
        before = dict(inventory.stock)
        self.assertFalse(orders.purchase("invalid", {"a": -1}))
        self.assertEqual(inventory.stock, before)
'''

MUTATIONS = {
    'payment_rollback_removed': ('        for k, q in items.items():\n            inventory.stock[k] += q\n', ''),
    'duplicate_guard_removed': ('    if order_id in processed:\n        return False\n', ''),
    'partial_inventory_decrement': ('    if any(q <= 0 or stock.get(k, 0) < q for k, q in items.items()):\n        return False\n    for k, q in items.items():\n        stock[k] -= q\n', '    for k, q in items.items():\n        if q <= 0 or stock.get(k, 0) < q:\n            return False\n        stock[k] -= q\n'),
}

def write_repo(path, mutation=None):
    for name, source in FILES.items():
        if mutation:
            old, new = MUTATIONS[mutation]
            if old in source:
                source = source.replace(old, new, 1)
        (path / name).write_text(source, encoding='utf-8')

def run():
    with tempfile.TemporaryDirectory(prefix='retrace-multifile-') as tmp:
        repo = Path(tmp)
        write_repo(repo)
        baseline = {'public_pass': verify(repo, PUBLIC), 'heldout_pass': verify(repo, HELDOUT)}
        rows = []
        for name in MUTATIONS:
            write_repo(repo)
            write_repo(repo, name)
            rows.append({'mutation': name, 'public_pass': verify(repo, PUBLIC),
                         'heldout_pass': verify(repo, HELDOUT)})
    return {'kind': 'offline_verifier_sensitivity', 'agent_evaluated': False,
            'baseline': baseline, 'mutants': rows,
            'limitations': ['Synthetic three-module fixture', 'No concurrency or crash-consistency claims',
                            'No model calls or repair comparisons', 'Trusted local code only; not a sandbox']}

if __name__ == '__main__':
    print(json.dumps(run(), indent=2))
