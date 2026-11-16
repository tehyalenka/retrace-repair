"""Offline JSON-mode and experiment regression tests."""
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from codepilot.agent import ask_model, parse_edits_with_format_retry

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("json_mode_experiment", ROOT / "benchmarks/v11/json_mode_experiment.py")
# Runner imports evaluate from its directory.
import sys
sys.path.insert(0, str(ROOT / "benchmarks/v11"))
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class JsonModeExperimentTests(unittest.TestCase):
    def test_request_mode_override(self):
        response = Mock(status_code=200)
        response.json.return_value = {"choices": [{"message": {"content": '{"edits": []}'}}]}
        with patch("codepilot.agent.provider_config", return_value=("secret", "test-model", "https://example.test")), \
             patch("codepilot.agent.requests.post", return_value=response) as post, \
             patch.dict("os.environ", {"CODEPILOT_JSON_MODE": "1"}):
            ask_model([{"role": "user", "content": "test"}], json_mode=False)
            self.assertNotIn("response_format", post.call_args.kwargs["json"])
            ask_model([{"role": "user", "content": "test"}], json_mode=True)
            self.assertEqual(post.call_args.kwargs["json"]["response_format"], {"type": "json_object"})

    def test_format_repair_diagnostics(self):
        diagnostics = {}
        valid = json.dumps({"edits": [{"path": "x.py", "content": "x=1\n"}]})
        with patch("codepilot.agent.ask_model", return_value=valid) as model:
            parsed = parse_edits_with_format_retry([], "not json", diagnostics=diagnostics, json_mode=True)
        self.assertEqual(parsed["edits"][0]["path"], "x.py")
        self.assertEqual(diagnostics["format_retries_used"], 1)
        self.assertTrue(diagnostics["format_repair_succeeded"])
        self.assertTrue(model.call_args.kwargs["json_mode"])

    def test_summary(self):
        report = {"cases": [{"success": True, "first_attempt_passed": False, "elapsed_seconds": 12,
                             "history": [{"failure_category": "malformed_edit_json", "format_retries_used": 2},
                                         {"passed": True, "format_retries_used": 1, "format_repair_succeeded": True}]}]}
        result = module.summarize(report)
        self.assertEqual(result["malformed_json_attempts"], 1)
        self.assertEqual(result["format_retries"], 3)
        self.assertEqual(result["format_repairs_succeeded"], 1)

    def test_runner_both_modes(self):
        import tempfile
        calls = []
        def evaluator(names, attempts, generated, output, agent):
            calls.append(str(output))
            return {"cases": [{"success": True, "first_attempt_passed": True, "elapsed_seconds": 1, "history": []}]}
        with tempfile.TemporaryDirectory() as directory:
            result = module.run_experiment(2, 1, directory, evaluator=evaluator)
            self.assertEqual(len(calls), 4)
            self.assertEqual(len(result["runs"]), 4)
            self.assertTrue((Path(directory) / "comparison.json").exists())


if __name__ == "__main__":
    unittest.main()
