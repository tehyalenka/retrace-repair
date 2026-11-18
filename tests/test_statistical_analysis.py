"""Unit tests for statistical analysis and experiment manifest tools."""
import json
import tempfile
import unittest
from pathlib import Path

from benchmarks.v18.statistical_analysis import (
    analyze_directory,
    bootstrap_ci,
    mcnemar_exact_p_value,
)
from benchmarks.v18.experiment_manifest import (
    generate_manifest,
    generate_run_manifest,
    get_git_provenance,
    seal_evidence_manifest,
    verify_run_manifest,
)


class StatisticalAnalysisTests(unittest.TestCase):

    def test_bootstrap_ci_basic_properties(self):
        vals = [1.0] * 10
        mean, low, high = bootstrap_ci(vals)
        self.assertEqual(mean, 1.0)
        self.assertEqual(low, 1.0)
        self.assertEqual(high, 1.0)

    def test_bootstrap_ci_variance(self):
        vals = [0.0] * 10 + [1.0] * 10
        mean, low, high = bootstrap_ci(vals)
        self.assertEqual(mean, 0.5)
        self.assertLess(low, 0.5)
        self.assertGreater(high, 0.5)

    def test_mcnemar_exact_p_value_symmetric(self):
        # When discordance is balanced, p-value should be 1.0
        self.assertEqual(mcnemar_exact_p_value(5, 5), 1.0)

    def test_mcnemar_exact_p_value_zero_discordance(self):
        self.assertEqual(mcnemar_exact_p_value(0, 0), 1.0)

    def test_mcnemar_exact_p_value_extreme(self):
        # 10 successes in A vs 0 in B
        p_val = mcnemar_exact_p_value(10, 0)
        self.assertLess(p_val, 0.01)

    def test_experiment_manifest_generation(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "manifest.json"
            data = generate_manifest(str(out))
            self.assertTrue(out.exists())
            self.assertGreaterEqual(data["manifest_schema"], 1)
            self.assertIn("git_provenance", data)
            self.assertIn("task_inputs", data["benchmark_metadata"])
            self.assertEqual(data["benchmark_metadata"]["total_tasks"], 45)

    def test_mcnemar_drops_unpaired_tasks_cleanly(self):
        """Verify that tasks missing in either arm are dropped rather than imputed as failure."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            # Create task 1: has both resample and feedback
            t1 = {
                "rows": [
                    {"condition": "resample", "success": True, "heldout": {"passed": True}, "live_calls": 1},
                    {"condition": "feedback", "success": True, "heldout": {"passed": False}, "live_calls": 1},
                ]
            }
            # Create task 2: only has resample
            t2 = {
                "rows": [
                    {"condition": "resample", "success": True, "heldout": {"passed": True}, "live_calls": 1},
                ]
            }
            (tmp_path / "t1-live.json").write_text(json.dumps(t1), encoding="utf-8")
            (tmp_path / "t2-live.json").write_text(json.dumps(t2), encoding="utf-8")

            report = analyze_directory(str(tmp_path))
            pair = report["mcnemar_paired_tests"]["resample_vs_feedback"]
            self.assertEqual(pair["paired_evaluable_tasks"], 1)
            self.assertIn("t2", pair["dropped_missing_strategy_tasks"])
            self.assertEqual(pair["resample_only_pass"], 1)

    def test_rejects_duplicate_strategy_row(self):
        """Verify duplicate condition rows in a single task raise ValueError."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            bad_task = {
                "rows": [
                    {"condition": "resample", "success": True, "heldout": {"passed": True}, "live_calls": 1},
                    {"condition": "resample", "success": False, "heldout": {"passed": False}, "live_calls": 1},
                ]
            }
            (tmp_path / "dup-live.json").write_text(json.dumps(bad_task), encoding="utf-8")
            with self.assertRaises(ValueError) as ctx:
                analyze_directory(str(tmp_path))
            self.assertIn("Duplicate strategy row", str(ctx.exception))

    def test_rejects_malformed_json_file(self):
        """Verify malformed JSON files raise ValueError with clear filename."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "corrupt-live.json").write_text("{ unclosed json: ", encoding="utf-8")
            with self.assertRaises(ValueError) as ctx:
                analyze_directory(str(tmp_path))
            self.assertIn("Malformed benchmark JSON file", str(ctx.exception))

    def test_token_accounting_separation(self):
        """Verify provider_reported_tokens is separated from heuristic estimated_tokens."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            provider_task = {
                "rows": [
                    {
                        "condition": "resample",
                        "success": True,
                        "heldout": {"passed": True},
                        "live_calls": 1,
                        "request_accounting": {"prompt_tokens": 100, "completion_tokens": 50},
                    }
                ]
            }
            (tmp_path / "p-live.json").write_text(json.dumps(provider_task), encoding="utf-8")
            report = analyze_directory(str(tmp_path))
            stats = report["summary_statistics"]["resample"]
            self.assertEqual(stats["provider_reported_tokens"], 150)
            self.assertIsNone(stats["estimated_tokens"])
            self.assertEqual(stats["token_accounting_mode"], "provider_verified")

    def test_manifest_lifecycle_run_and_evidence_seal(self):
        """Test the two-record lifecycle: run-manifest before execution and evidence-manifest after."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            run_manifest_file = tmp_path / "run-manifest.json"
            cfg = {
                "model_id": "test-model-42",
                "temperature_resample": 0.7,
                "temperature_repair": 0.0,
            }
            # 1. Pre-run manifest generation
            run_data = generate_run_manifest(run_manifest_file, config=cfg)
            self.assertTrue(run_manifest_file.exists())
            self.assertEqual(run_data["lifecycle_stage"], "pre_run_snapshot")
            self.assertEqual(run_data["effective_configuration"]["model_id"], "test-model-42")

            # 2. Resume verification passes when inputs match
            self.assertTrue(verify_run_manifest(run_manifest_file, current_config=cfg))

            # 3. Simulate outputs and seal evidence
            (tmp_path / "t1-live.json").write_text(json.dumps({"rows": []}), encoding="utf-8")
            (tmp_path / "summary.json").write_text(json.dumps({"completed": 1}), encoding="utf-8")
            evidence_file = tmp_path / "evidence-manifest.json"

            evidence_data = seal_evidence_manifest(tmp_path, run_manifest_file, output_path=evidence_file)
            self.assertTrue(evidence_file.exists())
            self.assertEqual(evidence_data["lifecycle_stage"], "post_run_evidence_seal")
            self.assertEqual(evidence_data["run_id"], run_data["run_id"])
            self.assertEqual(evidence_data["run_manifest_sha256"], run_data["run_manifest_sha256"])
            self.assertIn("t1-live.json", evidence_data["output_artifacts"])
            self.assertIn("summary.json", evidence_data["output_artifacts"])
            self.assertGreaterEqual(evidence_data["total_artifacts_sealed"], 2)

    def test_resume_verification_detects_fixture_tampering(self):
        """Verify that verify_run_manifest detects if a task fixture has been modified."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            run_manifest_file = tmp_path / "run-manifest.json"
            generate_run_manifest(run_manifest_file)

            # Tamper with the saved input hash
            data = json.loads(run_manifest_file.read_text(encoding="utf-8"))
            t_first = next(iter(data["benchmark_metadata"]["task_inputs"].keys()))
            data["benchmark_metadata"]["task_inputs"][t_first]["public_verifier_sha256"] = "tampered_hash_0000"
            run_manifest_file.write_text(json.dumps(data), encoding="utf-8")

            with self.assertRaises(ValueError) as ctx:
                verify_run_manifest(run_manifest_file)
            self.assertIn("public verifier changed", str(ctx.exception))

    def test_git_provenance_resolution(self):
        """Verify git provenance resolution handles commit SHA and method tracking."""
        sha, dirty, method, pub_grade = get_git_provenance()
        self.assertIsInstance(sha, str)
        self.assertIn(method, ["git_cli", "loose_ref_file", "packed_refs_file", "detached_head_file", "reflog_file", "unverified_fallback"])
        self.assertIsInstance(pub_grade, bool)


if __name__ == "__main__":
    unittest.main()
