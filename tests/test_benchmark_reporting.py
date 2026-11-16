import json
import tempfile
import unittest
from pathlib import Path

from evaluation.generate_report import generate_report


class BenchmarkReportingTests(unittest.TestCase):

    def make_report(self, result):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)

        root = Path(temporary.name)
        run_id = "123456abcdef"

        directory = root / ".codepilot-runs" / run_id
        directory.mkdir(parents=True)

        run = {
            "id": run_id,
            "repository": "sample",
            "task": "Implement feature",
            "status": "completed",
            "result": result,
        }

        (directory / "run.json").write_text(
            json.dumps(run), encoding="utf-8"
        )

        _, report = generate_report(root, run_id)
        return report

    def test_success_without_evidence(self):
        report = self.make_report({
            "success": True,
            "history": [{"attempt": 1, "passed": True}],
            "files": {"example.py": "value = 2\n"},
        })

        self.assertEqual(
            report["outcome"],
            "reported_success_unverified",
        )

    def test_smoke_tests_passed(self):
        report = self.make_report({
            "success": True,
            "history": [{
                "attempt": 1,
                "passed": True,
                "tests_run": 3,
            }],
            "files": {"example.py": "value = 2\n"},
        })

        self.assertEqual(
            report["outcome"],
            "smoke_tests_passed",
        )

    def test_provider_failure(self):
        report = self.make_report({
            "success": False,
            "history": [{
                "attempt": 1,
                "passed": False,
                "failure_category": "provider_error",
                "failure_stage": "model_request",
            }],
            "files": {},
        })

        self.assertEqual(
            report["outcome"],
            "provider_failure",
        )

    def test_agent_test_failure(self):
        report = self.make_report({
            "success": False,
            "history": [{
                "attempt": 1,
                "passed": False,
                "failure_category": "test_failure",
                "failure_stage": "smoke_tests",
            }],
            "files": {},
        })

        self.assertEqual(
            report["outcome"],
            "agent_test_failure",
        )

    def test_no_history(self):
        report = self.make_report({
            "success": False,
            "history": [],
            "files": {},
        })

        self.assertEqual(
            report["outcome"],
            "not_evaluated",
        )

    def test_invalid_run_id(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                generate_report(directory, "../unsafe")


    def test_saved_independent_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run_id = "123456abcdef"
            run_dir = root / ".codepilot-runs" / run_id
            run_dir.mkdir(parents=True)

            (run_dir / "run.json").write_text(json.dumps({
                "repository": "sample",
                "task": "Implement feature",
                "result": {
                    "success": True,
                    "history": [{"attempt": 1, "passed": True}],
                    "files": {"example.py": "x = 1"},
                },
            }))

            (run_dir / "verification.json").write_text(json.dumps({
                "passed": True,
                "returncode": 0,
                "timed_out": False,
                "applied_files": ["example.py"],
                "output": "Ran 5 tests\\nOK",
            }))

            _, report = generate_report(root, run_id)

            self.assertEqual(
                report["outcome"],
                "independent_verification_passed",
            )
            self.assertTrue(
                report["independent_verification"]["passed"]
            )

    def test_failed_independent_verification_not_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run_id = "123456abcdef"
            run_dir = root / ".codepilot-runs" / run_id
            run_dir.mkdir(parents=True)

            (run_dir / "run.json").write_text(json.dumps({
                "result": {
                    "success": True,
                    "history": [{"attempt": 1, "passed": True}],
                    "files": {},
                },
            }))

            (run_dir / "verification.json").write_text(json.dumps({
                "passed": False,
                "returncode": 1,
                "timed_out": False,
                "output": "FAIL",
            }))

            _, report = generate_report(root, run_id)

            self.assertFalse(
                report["independent_verification"]["passed"]
            )
            self.assertNotEqual(
                report["outcome"],
                "independent_verification_passed",
            )


    def test_failed_verification_overrides_smoke_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run_id = "123456abcdef"
            run_dir = root / ".codepilot-runs" / run_id
            run_dir.mkdir(parents=True)

            (run_dir / "run.json").write_text(json.dumps({
                "result": {
                    "success": True,
                    "history": [{
                        "attempt": 1,
                        "passed": True,
                        "tests_run": 3
                    }],
                    "files": {"example.py": "x = 1"}
                }
            }), encoding="utf-8")

            (run_dir / "verification.json").write_text(json.dumps({
                "passed": False,
                "returncode": 1,
                "timed_out": False,
                "output": "FAILED"
            }), encoding="utf-8")

            _, report = generate_report(root, run_id)

            self.assertEqual(
                report["outcome"],
                "independent_verification_failed"
            )

    def test_timed_out_verification_is_not_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run_id = "123456abcdef"
            run_dir = root / ".codepilot-runs" / run_id
            run_dir.mkdir(parents=True)

            (run_dir / "run.json").write_text(json.dumps({
                "result": {
                    "success": True,
                    "history": [{
                        "attempt": 1,
                        "passed": True,
                        "tests_run": 3
                    }],
                    "files": {"example.py": "x = 1"}
                }
            }), encoding="utf-8")

            (run_dir / "verification.json").write_text(json.dumps({
                "passed": False,
                "returncode": None,
                "timed_out": True,
                "output": "Verification timed out"
            }), encoding="utf-8")

            _, report = generate_report(root, run_id)

            self.assertEqual(
                report["outcome"],
                "independent_verification_failed"
            )


    def test_smoke_success_with_overall_failure(self):
        report = self.make_report({
            "success": False,
            "history": [{
                "attempt": 1,
                "passed": False,
                "tests_run": 3,
                "smoke_tests_passed": True,
                "smoke_tests_run": 3,
                "verification_passed": False,
                "failure_category": "test_failure",
                "failure_stage": "independent_verification",
            }],
            "files": {},
        })

        self.assertTrue(report["smoke_tests"]["passed"])
        self.assertEqual(report["smoke_tests"]["tests_run"], 3)
        self.assertEqual(report["outcome"], "agent_test_failure")

    def test_legacy_run_does_not_infer_smoke_success(self):
        report = self.make_report({
            "success": True,
            "history": [{
                "attempt": 1,
                "passed": True,
                "tests_run": 3,
            }],
            "files": {},
        })

        self.assertIsNone(report["smoke_tests"]["passed"])
        self.assertIsNone(report["smoke_tests"]["tests_run"])


if __name__ == "__main__":
    unittest.main()
