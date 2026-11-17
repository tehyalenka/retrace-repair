import unittest

from benchmarks.v18 import research_report


def make_record(
    task,
    arm,
    status="completed",
    http_requests=None,
    prompt_tokens=None,
    completion_tokens=None,
    usage_reports=None,
):
    completed = status == "completed"

    return {
        "task": task,
        "category": "bugfix",
        "arm": arm,
        "repetition": 1,
        "status": status,
        "public": True if completed else None,
        "heldout": True if completed else None,
        "combined": True if completed else None,
        "calls": 0,
        "infrastructure_warning": False,
        "http_requests": http_requests,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "usage_reports": usage_reports,
    }


class ResearchResourceTests(unittest.TestCase):

    def test_mixed_known_and_unknown_usage(self):
        records = [
            make_record(
                "task_a", "resample",
                http_requests=3,
                prompt_tokens=120,
                completion_tokens=40,
                usage_reports=1,
            ),
            make_record("task_b", "resample"),
        ]

        result = research_report.summarize(records)
        usage = result["resource_usage"]["resample"]

        self.assertEqual(usage["http_known_evaluations"], 1)
        self.assertEqual(usage["http_unknown_evaluations"], 1)
        self.assertEqual(usage["known_http_requests"], 3)
        self.assertEqual(usage["token_observed_evaluations"], 1)
        self.assertEqual(usage["observed_prompt_tokens"], 120)
        self.assertEqual(usage["observed_completion_tokens"], 40)

    def test_known_zero_is_not_unknown(self):
        records = [
            make_record(
                "task_a", "feedback",
                http_requests=0,
                prompt_tokens=0,
                completion_tokens=0,
                usage_reports=0,
            )
        ]

        result = research_report.summarize(records)
        usage = result["resource_usage"]["feedback"]

        self.assertEqual(usage["http_known_evaluations"], 1)
        self.assertEqual(usage["http_unknown_evaluations"], 0)
        self.assertEqual(usage["known_http_requests"], 0)

        # Zero usage reports does not establish token usage.
        self.assertEqual(usage["token_observed_evaluations"], 0)
        self.assertIsNone(usage["observed_prompt_tokens"])
        self.assertIsNone(usage["observed_completion_tokens"])

    def test_pending_reservations_are_counted(self):
        records = [
            make_record(
                "task_a", "counterfactual",
                status="pending",
                http_requests=2,
            ),
            make_record(
                "task_b", "counterfactual",
                http_requests=4,
                prompt_tokens=90,
                completion_tokens=30,
                usage_reports=1,
            ),
        ]

        result = research_report.summarize(records)
        usage = result["resource_usage"]["counterfactual"]
        strategy = result["strategies"]["counterfactual"]

        self.assertEqual(usage["known_http_requests"], 6)
        self.assertEqual(usage["http_known_evaluations"], 2)
        self.assertEqual(strategy["pending"], 1)
        self.assertEqual(strategy["completed"], 1)

        # Pending is not counted as a successful repair.
        self.assertEqual(strategy["combined_pass"], 1)


if __name__ == "__main__":
    unittest.main()
