import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from codepilot.agent import run_agent


class SmokeEvidenceTests(unittest.TestCase):

    def test_smoke_success_preserved_when_verification_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)

            (repo / "calc.py").write_text(
                "def double(x):\n"
                "    return x\n",
                encoding="utf-8",
            )

            tests_dir = repo / "tests"
            tests_dir.mkdir()

            (tests_dir / "test_calc.py").write_text(
                "import unittest\n"
                "from calc import double\n"
                "class CalcTests(unittest.TestCase):\n"
                "    def test_double(self):\n"
                "        self.assertEqual(double(3), 6)\n",
                encoding="utf-8",
            )

            response = json.dumps({
                "edits": [{
                    "path": "calc.py",
                    "operation": "modify",
                    "content": (
                        "def double(x):\n"
                        "    return x * 2\n"
                    ),
                }]
            })

            verifier = (
                "import unittest\n"
                "from calc import double\n"
                "class IndependentTests(unittest.TestCase):\n"
                "    def test_negative_input(self):\n"
                "        self.assertEqual(double(-2), 0)\n"
            )

            with patch(
                "codepilot.agent.ask_model",
                return_value=response,
            ) as model:
                result = run_agent(
                    repo,
                    "Implement double",
                    attempts=1,
                    verification=verifier,
                )

            model.assert_called_once()

            self.assertFalse(result["success"])
            self.assertEqual(len(result["history"]), 1)

            attempt = result["history"][0]

            self.assertTrue(attempt["smoke_tests_passed"])
            self.assertEqual(attempt["smoke_tests_run"], 1)

            self.assertFalse(attempt["verification_passed"])
            self.assertFalse(attempt["passed"])

            self.assertEqual(
                attempt["failure_stage"],
                "independent_verification",
            )

            self.assertEqual(
                attempt["failure_category"],
                "test_failure",
            )

            # Original repository must remain unchanged.
            self.assertEqual(
                (repo / "calc.py").read_text(encoding="utf-8"),
                "def double(x):\n    return x\n",
            )


if __name__ == "__main__":
    unittest.main()
