"""Paired multi-file evaluation for CodePilot-X. Python 3.9+.

Baseline and verification conditions start from identical repository snapshots.
The verifier is independently authored; hidden tests are never shown to the agent.
Run only trusted code: this is not a sandbox.
"""
import argparse
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time

from codepilot.agent import run_agent


TASKS = [
    {
        "id": "discount_rounding",
        "task": "Fix the checkout total: percentage discounts must apply before tax, and totals must be rounded to 2 decimal places. Preserve the public checkout_total API.",
        "files": {
            "pricing.py": "def discounted(price, percent):\n    return price * (1 - percent / 100)\n",
            "checkout.py": "from pricing import discounted\n\ndef checkout_total(price, discount_percent, tax_percent):\n    return round(price * (1 + tax_percent / 100) - discounted(price, discount_percent), 2)\n",
        },
        "verification": "from checkout import checkout_total\nimport unittest\nclass Verification(unittest.TestCase):\n    def test_discount_before_tax(self):\n        self.assertEqual(checkout_total(100, 20, 10), 88.0)\n",
        "hidden": "from checkout import checkout_total\nimport unittest\nclass Hidden(unittest.TestCase):\n    def test_zero_discount(self): self.assertEqual(checkout_total(100, 0, 10), 110.0)\n    def test_zero_tax(self): self.assertEqual(checkout_total(100, 25, 0), 75.0)\n    def test_both(self): self.assertEqual(checkout_total(200, 10, 5), 189.0)\n",
    },
    {
        "id": "permissions_service",
        "task": "Fix can_edit so an owner can edit their own document and an admin can edit any document. Viewers cannot edit. Preserve can_edit(user, document) API.",
        "files": {
            "models.py": "def is_admin(user):\n    return user.get('role') == 'admin'\n\ndef is_owner(user, document):\n    return user.get('id') == document.get('owner_id')\n",
            "permissions.py": "from models import is_admin, is_owner\n\ndef can_edit(user, document):\n    return is_admin(user) and is_owner(user, document)\n",
        },
        "verification": "from permissions import can_edit\nimport unittest\nclass Verification(unittest.TestCase):\n    def test_owner(self): self.assertTrue(can_edit({'id': 2, 'role': 'user'}, {'owner_id': 2}))\n    def test_admin(self): self.assertTrue(can_edit({'id': 1, 'role': 'admin'}, {'owner_id': 2}))\n",
        "hidden": "from permissions import can_edit\nimport unittest\nclass Hidden(unittest.TestCase):\n    def test_viewer(self): self.assertFalse(can_edit({'id': 1, 'role': 'viewer'}, {'owner_id': 2}))\n    def test_other_user(self): self.assertFalse(can_edit({'id': 3, 'role': 'user'}, {'owner_id': 2}))\n    def test_admin_owner(self): self.assertTrue(can_edit({'id': 1, 'role': 'admin'}, {'owner_id': 1}))\n",
    },
    {
        "id": "shipping_threshold",
        "task": "Fix order_total: free shipping applies when the discounted subtotal is at least 50, otherwise add 7 shipping. Return a numeric total rounded to two decimals.",
        "files": {
            "discounts.py": "def apply_discount(subtotal, discount):\n    return subtotal - discount\n",
            "orders.py": "from discounts import apply_discount\n\ndef order_total(subtotal, discount):\n    after_discount = apply_discount(subtotal, discount)\n    shipping = 0 if subtotal >= 50 else 7\n    return round(after_discount + shipping, 2)\n",
        },
        "verification": "from orders import order_total\nimport unittest\nclass Verification(unittest.TestCase):\n    def test_discount_changes_threshold(self): self.assertEqual(order_total(55, 10), 52.0)\n",
        "hidden": "from orders import order_total\nimport unittest\nclass Hidden(unittest.TestCase):\n    def test_boundary(self): self.assertEqual(order_total(60, 10), 50.0)\n    def test_below(self): self.assertEqual(order_total(50, 1), 56.0)\n    def test_above(self): self.assertEqual(order_total(70, 5), 65.0)\n",
    },
]


def make_repo(root, task):
    for name, source in task["files"].items():
        (root / name).write_text(source, encoding="utf-8")
    (root / "tests").mkdir()
    (root / "tests/test_smoke.py").write_text(
        "import unittest\nclass Smoke(unittest.TestCase):\n"
        "    def test_import(self):\n"
        "        import {}\n".format(next(iter(task["files"])).replace(".py", "")),
        encoding="utf-8")


def hidden_check(task, files):
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        for name, source in task["files"].items():
            (root / name).write_text(files.get(name, source), encoding="utf-8")
        (root / "tests").mkdir()
        (root / "tests/test_hidden.py").write_text(task["hidden"], encoding="utf-8")
        try:
            p = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
                               cwd=str(root), capture_output=True, text=True, timeout=15,
                               env={**os.environ, "PYTHONPATH": str(root)})
            return p.returncode == 0 and "Ran 0 tests" not in p.stderr, (p.stdout + p.stderr)[-1500:]
        except subprocess.TimeoutExpired:
            return False, "Hidden tests timed out"


def evaluate(limit, attempts, repeats, output):
    rows = []
    for repeat in range(repeats):
        for task in TASKS[:limit]:
            for condition in ("baseline", "verification"):
                with tempfile.TemporaryDirectory() as d:
                    root = Path(d)
                    make_repo(root, task)
                    started = time.monotonic()
                    row = {"task": task["id"], "repeat": repeat + 1, "condition": condition}
                    try:
                        result = run_agent(root, task["task"], attempts=attempts, max_files=6,
                                           verification=task["verification"] if condition == "verification" else None)
                        row["agent_pass"] = result["success"]
                        row["attempts"] = len(result["history"])
                        row["hidden_pass"], row["hidden_feedback"] = hidden_check(task, result["files"])
                        row["history"] = result["history"]
                    except Exception as exc:
                        row.update(agent_pass=False, hidden_pass=False, error=str(exc)[:800])
                    row["seconds"] = round(time.monotonic() - started, 3)
                    rows.append(row)
                    print("{} repeat={} {} hidden={}".format(task["id"], repeat + 1, condition, row["hidden_pass"]), flush=True)
    rates = {}
    for condition in ("baseline", "verification"):
        selected = [r for r in rows if r["condition"] == condition]
        rates[condition] = {"completed": len(selected), "hidden_success_rate": sum(r["hidden_pass"] for r in selected) / len(selected) if selected else None,
                            "mean_seconds": statistics.mean(r["seconds"] for r in selected) if selected else None}
    report = {"benchmark": "CodePilot-X v0.6 multi-file paired synthetic study", "model": os.getenv("CODEPILOT_MODEL", "provider default"),
              "provider": os.getenv("CODEPILOT_PROVIDER", "groq"), "repeats": repeats, "attempts_limit": attempts,
              "rates": rates, "results": rows,
              "limitations": ["Small synthetic tasks, not SWE-bench", "Hand-authored verifier tests, not LLM-generated", "No security sandbox", "Repeat trials may not be statistically independent", "Model and API availability may change"]}
    Path(output).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=3, choices=range(1, 4))
    parser.add_argument("--attempts", type=int, default=2, choices=range(1, 6))
    parser.add_argument("--repeats", type=int, default=1, choices=range(1, 11))
    parser.add_argument("--output", default="benchmark-v06.json")
    args = parser.parse_args()
    print(json.dumps(evaluate(args.limit, args.attempts, args.repeats, args.output)["rates"], indent=2))
