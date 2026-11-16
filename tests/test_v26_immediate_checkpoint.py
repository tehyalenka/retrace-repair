"""Offline regression tests for immediate persistence of model completions."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import benchmarks.v22.natural_recovery as recovery
import codepilot.agent as agent


class ImmediateCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / 'repo'
        self.repo.mkdir()
        self.verifier = 'verification code'
        self.trace = {
            'mode': 'live', 'case': 'bugfix', 'task': 'fix',
            'repo_sha256': 'fixture-fingerprint',
            'verifier_sha256': hashlib.sha256(self.verifier.encode()).hexdigest(),
            'first_attempt': {'failure_category': 'test_failure'},
            'calls': [{'response': 'first failed completion'}],
        }

    def test_fresh_completion_is_checkpointed_before_crash_and_replayed(self):
        snapshots = []
        network_calls = []

        def model(*args, **kwargs):
            network_calls.append(True)
            return 'saved completion'

        def crash_after_completion(*args, **kwargs):
            agent.ask_model([{'role': 'user', 'content': 'initial'}])
            agent.ask_model([{'role': 'user', 'content': 'next'}])
            raise RuntimeError('simulated process interruption')

        with patch.object(recovery, 'task_setup', return_value=(self.repo, 'fix', self.verifier)), \
             patch.object(recovery, 'fingerprint', return_value='fixture-fingerprint'), \
             patch.object(agent, 'ask_model', side_effect=model), \
             patch.object(agent, 'run_agent', side_effect=crash_after_completion):
            with self.assertRaisesRegex(RuntimeError, 'simulated process interruption'):
                recovery.run_arm(self.trace, 'resample', checkpoint=snapshots.append)
        self.assertEqual(len(network_calls), 1)
        self.assertEqual(len(snapshots), 1)
        saved = snapshots[0]
        self.assertTrue(saved['checkpoint_incomplete'])
        self.assertTrue(saved['provider_failure'])
        self.assertEqual(saved['model_calls'][1]['response'], 'saved completion')

        def resume_agent(*args, **kwargs):
            self.assertEqual(agent.ask_model([{'role': 'user', 'content': 'initial'}]), 'first failed completion')
            self.assertEqual(agent.ask_model([{'role': 'user', 'content': 'next'}]), 'saved completion')
            return {'success': True, 'history': [{'failure_category': 'test_failure'}]}

        with patch.object(recovery, 'task_setup', return_value=(self.repo, 'fix', self.verifier)), \
             patch.object(recovery, 'fingerprint', return_value='fixture-fingerprint'), \
             patch.object(agent, 'ask_model', side_effect=model), \
             patch.object(agent, 'run_agent', side_effect=resume_agent):
            result = recovery.run_arm(self.trace, 'resample', prior=saved)
        self.assertTrue(result['success'])
        self.assertEqual(result['replayed_saved_calls'], 1)
        self.assertEqual(len(network_calls), 1)

    def test_evaluator_persists_partial_arm_before_exception(self):
        output = Path(self.temp.name) / 'result.json'
        trace = dict(self.trace)

        def capture(mode, case, path):
            Path(path).write_text(json.dumps(trace))
            return dict(trace, capture_success=False)

        def interrupt(*args, **kwargs):
            agent.ask_model([{'role': 'user', 'content': 'first'}])
            agent.ask_model([{'role': 'user', 'content': 'second'}])
            raise RuntimeError('simulated crash after model response')

        with patch.object(recovery, 'task_setup', return_value=(self.repo, 'fix', self.verifier)), \
             patch.object(recovery, 'fingerprint', return_value='fixture-fingerprint'), \
             patch.object(agent, 'ask_model', return_value='saved completion'), \
             patch.object(agent, 'run_agent', side_effect=interrupt):
            report = recovery.evaluate(mode='live', cases=('bugfix',), repeats=1,
                                       output=str(output), capture_fn=capture, cooldown=0)
        self.assertEqual(report['status'], 'incomplete')
        disk = json.loads(output.read_text())
        saved = disk['runs'][0]['arms']['resample']
        self.assertTrue(saved['checkpoint_incomplete'])
        self.assertEqual(saved['model_calls'][1]['response'], 'saved completion')
        self.assertEqual(disk['summary']['conditions']['resample']['completed'], 0)

        def resume(*args, **kwargs):
            self.assertEqual(agent.ask_model([{'role': 'user', 'content': 'first'}]), 'first failed completion')
            self.assertEqual(agent.ask_model([{'role': 'user', 'content': 'second'}]), 'saved completion')
            return {'success': True, 'history': [{'failure_category': 'test_failure'}]}

        # Only the resample arm has a saved continuation; the other arm would
        # require a new model request, so stop after verifying the replay.
        class StopAfterReplay(Exception):
            pass

        def resume_then_stop(*args, **kwargs):
            if kwargs.get('repair_feedback'):
                raise StopAfterReplay()
            return resume(*args, **kwargs)

        with patch.object(recovery, 'task_setup', return_value=(self.repo, 'fix', self.verifier)), \
             patch.object(recovery, 'fingerprint', return_value='fixture-fingerprint'), \
             patch.object(agent, 'ask_model', side_effect=AssertionError('Unexpected API request')), \
             patch.object(agent, 'run_agent', side_effect=resume_then_stop):
            resumed = recovery.evaluate(mode='live', cases=('bugfix',), repeats=1,
                                        output=str(output), capture_fn=capture,
                                        cooldown=0, resume=True)
        self.assertTrue(resumed['runs'][0]['arms']['resample']['success'])
        self.assertEqual(resumed['runs'][0]['arms']['resample']['replayed_saved_calls'], 1)
        self.assertEqual(resumed['summary']['conditions']['resample']['completed'], 1)


if __name__ == '__main__':
    unittest.main()
