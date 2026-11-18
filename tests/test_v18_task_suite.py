import unittest
from benchmarks.v18.task_suite_runner import validate, tasks

ORIGINAL_IDS = {
    'clamp_bounds', 'deduplicate', 'average_empty', 'normalize_whitespace',
    'slugify', 'running_total', 'group_counts', 'refactor_sort',
    'refactor_default', 'refactor_copy', 'multifile_discount',
    'multifile_tax', 'multifile_inventory', 'regression_negative',
    'regression_case',
}
ENTERPRISE_IDS = {
    'enterprise_order_atomicity', 'enterprise_ledger_exactly_once',
    'enterprise_tenant_cache', 'enterprise_bank_transfer',
    'enterprise_circuit_breaker', 'enterprise_saga_coordinator',
    'enterprise_rate_limiter_token_bucket', 'enterprise_wal_replay',
    'enterprise_two_phase_commit', 'enterprise_event_sourcing_aggregate',
    'enterprise_distributed_lock_lease', 'enterprise_optimistic_concurrency_doc',
    'enterprise_read_write_lock_fair', 'enterprise_crdt_pn_counter',
    'enterprise_idempotent_event_consumer', 'enterprise_dead_letter_retry',
    'enterprise_cache_stampede_mutex', 'enterprise_bulkhead_isolation',
    'enterprise_outbox_publisher', 'enterprise_secret_rotation_vault',
    'enterprise_tenant_rate_limiter', 'enterprise_audit_log_tamper_evident',
    'enterprise_rbac_policy_evaluator', 'enterprise_sliding_window_rate_limiter',
    'enterprise_connection_pool', 'enterprise_token_bucket_burst',
    'enterprise_adaptive_concurrency_limiter', 'enterprise_consistent_hash_ring',
    'enterprise_leader_epoch_election', 'enterprise_replicated_state_machine',
}
EXPECTED_IDS = ORIGINAL_IDS | ENTERPRISE_IDS
EXPECTED_CATEGORIES = {
    'bugfix', 'feature', 'refactor', 'multifile', 'regression', 'enterprise',
}


class TaskSuiteTests(unittest.TestCase):
    def test_manifest_categories(self):
        items = tasks()
        ids = [item['id'] for item in items]
        self.assertEqual(len(items), 45)
        self.assertEqual(len(set(ids)), len(ids), 'Duplicate benchmark IDs')
        self.assertEqual(set(ids), EXPECTED_IDS)
        self.assertEqual({item['category'] for item in items}, EXPECTED_CATEGORIES)
        self.assertEqual(
            {item['id'] for item in items if item['category'] == 'enterprise'},
            ENTERPRISE_IDS,
        )

    def test_all_public_failures_and_fixed_solutions(self):
        rows = validate()
        self.assertEqual(len(rows), len(EXPECTED_IDS))
        self.assertEqual({row['id'] for row in rows}, EXPECTED_IDS)
        for row in rows:
            with self.subTest(task=row['id']):
                self.assertFalse(row['initial_public_pass'])
                self.assertTrue(row['solution_public_pass'])
                self.assertTrue(row['solution_heldout_pass'])

    def test_fixture_isolation_no_heldout_or_solution_leakage(self):
        """Formally prove that held-out tests and reference solutions cannot leak into agent workspace."""
        import tempfile
        from pathlib import Path
        from benchmarks.v18.task_suite_runner import ROOT, fixture

        items = tasks()
        for item in items:
            with tempfile.TemporaryDirectory() as tmp:
                repo_dir = Path(tmp) / item["id"]
                fixture(item, repo_dir)

                # 1. No heldout files or solution directories exist in workspace
                all_relative_files = [str(p.relative_to(repo_dir)) for p in repo_dir.rglob("*")]
                self.assertFalse(any("heldout" in f.lower() for f in all_relative_files),
                                 f"Leakage detected: heldout test file found in {item['id']}")
                self.assertFalse(any("solution" in f.lower() for f in all_relative_files),
                                 f"Leakage detected: solution file/dir found in {item['id']}")

                # 2. None of the heldout verifier content appears in any workspace file
                heldout_text = (ROOT / item["heldout_verifier"]).read_text(encoding="utf-8").strip()
                for p in repo_dir.rglob("*.py"):
                    content = p.read_text(encoding="utf-8")
                    self.assertNotIn(heldout_text, content,
                                     f"Leakage detected: heldout verifier body found in {p}")

                # 3. Public test fixture exists strictly under tests/test_public.py
                public_test = repo_dir / "tests" / "test_public.py"
                self.assertTrue(public_test.exists())
                public_text = (ROOT / item["public_verifier"]).read_text(encoding="utf-8")
                self.assertEqual(public_test.read_text(encoding="utf-8"), public_text)
