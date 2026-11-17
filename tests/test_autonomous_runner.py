import unittest
from pathlib import Path
import tempfile
import json
from unittest.mock import patch, MagicMock

from benchmarks.v18.autonomous_runner import get_completed_tasks_count, is_benchmark_complete


class TestAutonomousRunner(unittest.TestCase):
    def test_task_counting(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            self.assertEqual(get_completed_tasks_count(p, 22), 0)
            self.assertFalse(is_benchmark_complete(p, 22))

            # create 1 completed file
            t1 = p / "task1-live.json"
            t1.write_text(json.dumps({
                "rows": [{"key": "1:resample"}, {"key": "1:feedback"}, {"key": "1:counterfactual"}],
                "pending": {}
            }))
            self.assertEqual(get_completed_tasks_count(p, 22), 1)

            # create incomplete file (with pending)
            t2 = p / "task2-live.json"
            t2.write_text(json.dumps({
                "rows": [{"key": "1:resample"}],
                "pending": {"1:feedback": []}
            }))
            self.assertEqual(get_completed_tasks_count(p, 22), 1)


if __name__ == "__main__":
    unittest.main()
