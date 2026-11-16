"""Offline regression checks for v2.4 replay; never contacts an LLM provider."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import benchmarks.v22.natural_recovery as recovery


class CheckpointReplayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        (self.repo / 'sample.py').write_text('x = 1\n', encoding='utf-8')
        self.task = 'Change sample.py'
        self.verifier = 'assert True\n'
        self.trace = {
            'mode': 'live', 'case': 'synthetic', 'task': self.task,
            'repo_sha256': recovery.fingerprint(self.repo),
            'verifier_sha256': hashlib.sha256(self.verifier.encode()).hexdigest(),
            'first_attempt': {'failure_category': 'test_failure'},
            'calls': [{'response': 'first failing response'}],
        }

    def run_arm(self, condition='resample', prior=None, fail_provider=False):
        observed = []
        def fake_agent(repo, task, attempts, verification, repair_feedback):
            self.assertEqual(task, self.task)
            self.assertEqual(verification, self.verifier)
            self.assertEqual(repair_feedback, condition == 'feedback')
            history = []
            for i in range(attempts):
                messages = [{'role': 'user', 'content':
                             'Tests/validation failed: details' if i and repair_feedback else 'Implement task'}]
                try:
                    response = recovery.agent.ask_model(messages)
                except RuntimeError:
                    history.append({'failure_category': 'provider_error', 'output': 'simulated failure'})
                    break
                observed.append(response)
                history.append({'failure_category': 'test_failure', 'output': 'failed'})
            return {'success': False, 'history': history}

        def no_network(*args, **kwargs):
            if fail_provider:
                raise RuntimeError('blocked provider call')
            return 'new completion'

        with patch.object(recovery, 'task_setup', return_value=(self.repo, self.task, self.verifier)), \
             patch.object(recovery.agent, 'run_agent', side_effect=fake_agent), \
             patch.object(recovery.agent, 'ask_model', side_effect=no_network) as api:
            result = recovery.run_arm(self.trace, condition, attempts=3, prior=prior)
        return result, observed, api.call_count

    def test_replays_saved_completion_before_new_request(self):
        prior = {'model_calls': [
            {'origin': 'replayed_natural_failure', 'response': 'first failing response'},
            {'origin': 'fresh_model_completion', 'response': 'saved completion'},
        ]}
        result, observed, calls = self.run_arm(prior=prior)
        self.assertEqual(observed, ['first failing response', 'saved completion', 'new completion'])
        self.assertEqual(calls, 1)
        self.assertEqual([c['origin'] for c in result['model_calls']],
                         ['replayed_natural_failure', 'replayed_saved_completion', 'fresh_model_completion'])
        self.assertEqual(result['replayed_saved_calls'], 1)

    def test_interrupted_replay_keeps_prior_response_and_records_failure(self):
        prior = {'model_calls': [
            {'origin': 'replayed_natural_failure', 'response': 'first failing response'},
            {'origin': 'fresh_model_completion', 'response': 'saved completion'},
        ]}
        result, observed, calls = self.run_arm(prior=prior, fail_provider=True)
        self.assertEqual(observed, ['first failing response', 'saved completion'])
        self.assertEqual(calls, 1)
        self.assertTrue(result['provider_failure'])
        self.assertEqual(result['replayed_saved_calls'], 1)

    def test_feedback_arm_marks_feedback_messages(self):
        result, observed, calls = self.run_arm(condition='feedback')
        self.assertEqual(calls, 2)
        self.assertEqual([c['feedback_message_present'] for c in result['model_calls']],
                         [False, True, True])

    def test_refuses_changed_verifier(self):
        self.trace['verifier_sha256'] = 'invalid'
        with patch.object(recovery, 'task_setup', return_value=(self.repo, self.task, self.verifier)), \
             patch.object(recovery.agent, 'ask_model') as api:
            with self.assertRaisesRegex(ValueError, 'Verifier changed'):
                recovery.run_arm(self.trace, 'resample')
            api.assert_not_called()

    def test_refuses_scripted_repairs_on_live_trace(self):
        with self.assertRaisesRegex(ValueError, 'Cannot use scripted offline'):
            recovery.run_arm(self.trace, 'resample', offline=True)


if __name__ == '__main__':
    unittest.main()
