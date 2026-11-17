import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from benchmarks.v18.research_gate import audit_pair


class ResearchGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.capture = root / 'case-capture.json'
        self.live = root / 'case-live.json'
        self.trace = {'case': 'case', 'repo_sha256': 'repo', 'verifier_sha256': 'public',
                      'first_attempt': {'failure_category': 'test_failure', 'tests_run': 1},
                      'calls': [{'response': '{}'}]}
        self.rows = [self.row(arm) for arm in ('resample', 'feedback', 'counterfactual')]
        self.save()

    def row(self, arm):
        return {'key': '1:' + arm, 'repetition': 1, 'condition': arm, 'success': True,
                'calls': [{'origin': 'captured_initial'}, {'origin': 'live'}], 'live_calls': 1,
                'history': [{'failure_category': 'test_failure', 'tests_run': 1}],
                'heldout': {'passed': True, 'tests_run': 2}}

    def save(self):
        self.capture.write_text(json.dumps(self.trace))
        self.report = {'settings': {'trace_sha256': hashlib.sha256(self.capture.read_bytes()).hexdigest(),
                                   'repo_sha256': 'repo', 'verifier_sha256': 'public',
                                   'heldout_sha256': 'heldout', 'repetitions': 1,
                                   'max_http_requests_per_arm': 2}, 'rows': self.rows}
        self.live.write_text(json.dumps(self.report))

    def test_valid_pair_is_integrity_valid_not_natural_failure_proof(self):
        r = audit_pair(self.capture, self.live)
        self.assertTrue(r['integrity_pass'])
        self.assertFalse(r['natural_model_failure_proven'])
        self.assertFalse(r['comparative_superiority_proven'])

    def test_tampered_capture_is_rejected(self):
        self.capture.write_text(self.capture.read_text() + ' ')
        self.assertFalse(audit_pair(self.capture, self.live)['integrity_pass'])

    def test_missing_arm_rejected(self):
        self.rows.pop()
        self.save()
        self.assertFalse(audit_pair(self.capture, self.live)['integrity_pass'])

    def test_duplicate_arm_rejected(self):
        self.rows.append(dict(self.rows[0]))
        self.save()
        self.assertFalse(audit_pair(self.capture, self.live)['integrity_pass'])

    def test_missing_heldout_rejected(self):
        self.rows[0]['heldout'] = None
        self.save()
        self.assertFalse(audit_pair(self.capture, self.live)['integrity_pass'])

    def test_public_only_success_rejected(self):
        self.rows[0]['heldout']['passed'] = False
        self.save()
        self.assertFalse(audit_pair(self.capture, self.live)['integrity_pass'])

    def test_wrong_call_accounting_rejected(self):
        self.rows[0]['live_calls'] = 5
        self.save()
        self.assertFalse(audit_pair(self.capture, self.live)['integrity_pass'])

    def test_unreproduced_first_failure_rejected(self):
        self.rows[0]['history'][0]['failure_category'] = 'provider_error'
        self.save()
        self.assertFalse(audit_pair(self.capture, self.live)['integrity_pass'])

    def test_no_executed_heldout_rejected(self):
        self.rows[0]['heldout']['tests_run'] = 0
        self.save()
        self.assertFalse(audit_pair(self.capture, self.live)['integrity_pass'])

    def test_mismatched_repo_rejected(self):
        self.report['settings']['repo_sha256'] = 'wrong'
        self.live.write_text(json.dumps(self.report))
        self.assertFalse(audit_pair(self.capture, self.live)['integrity_pass'])
