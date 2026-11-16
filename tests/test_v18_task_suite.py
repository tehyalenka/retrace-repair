import unittest
from benchmarks.v18.task_suite_runner import validate, tasks

class TaskSuiteTests(unittest.TestCase):
    def test_manifest_categories(self):
        items=tasks()
        self.assertEqual(len(items),15)
        self.assertEqual({x['category'] for x in items},
                         {'bugfix','feature','refactor','multifile','regression'})
        self.assertEqual(len({x['id'] for x in items}),15)

    def test_all_public_failures_and_fixed_solutions(self):
        rows=validate()
        self.assertEqual(len(rows),15)
        for row in rows:
            with self.subTest(task=row['id']):
                self.assertFalse(row['initial_public_pass'])
                self.assertTrue(row['solution_public_pass'])
                self.assertTrue(row['solution_heldout_pass'])
