"""Fail-closed, offline audit of three-arm benchmark evidence. No model calls.

This is a reporting gate, not a claim that the benchmark is statistically powered.
"""
import argparse
import hashlib
import json
from pathlib import Path

DEFAULT_ARMS = ('resample', 'feedback', 'counterfactual')
ALLOWED_CONDITIONS = ('resample', 'feedback', 'counterfactual', 'counterfactual_replay')


def audit_pair(capture_path, live_path):
    capture_path, live_path = Path(capture_path), Path(live_path)
    trace = json.loads(capture_path.read_text(encoding='utf-8'))
    report = json.loads(live_path.read_text(encoding='utf-8'))
    settings = report.get('settings', {})
    first = trace.get('first_attempt') or {}
    problems = []
    def require(condition, message):
        if not condition:
            problems.append(message)
    require(settings.get('trace_sha256') == hashlib.sha256(capture_path.read_bytes()).hexdigest(), 'capture digest mismatch')
    require(settings.get('repo_sha256') == trace.get('repo_sha256'), 'repository fingerprint mismatch')
    require(settings.get('verifier_sha256') == trace.get('verifier_sha256'), 'public verifier fingerprint mismatch')
    require(bool(settings.get('heldout_sha256')), 'held-out verifier fingerprint missing')
    require(first.get('failure_category') == 'test_failure' and first.get('tests_run', 0) > 0, 'initial failure not verified')
    require(bool(trace.get('calls')) and isinstance(trace['calls'][0].get('response'), str), 'captured completion missing')
    rows = report.get('rows', [])
    keys = [r.get('key') for r in rows]
    require(len(keys) == len(set(keys)), 'duplicate arm/repetition rows')
    reps = settings.get('repetitions', 0)
    arms_in_rows = tuple(dict.fromkeys(r.get('condition') for r in rows if r.get('condition') in ALLOWED_CONDITIONS))
    arms_used = arms_in_rows if len(arms_in_rows) >= 3 else DEFAULT_ARMS
    expected = {f'{rep}:{arm}' for rep in range(1, reps + 1) for arm in arms_used} if isinstance(reps, int) and reps > 0 else set()
    require(set(keys) == expected, 'incomplete or unexpected arm/repetition rows')
    for row in rows:
        key = row.get('key', '?')
        require(row.get('condition') in ALLOWED_CONDITIONS, f'{key}: invalid condition')
        require(row.get('key') == f"{row.get('repetition')}:{row.get('condition')}", f'{key}: inconsistent arm key')
        calls = row.get('calls', [])
        require(bool(calls) and calls[0].get('origin') in ('captured_initial', 'checkpoint_replay'), f'{key}: missing initial replay')
        require(bool(row.get('history')) and row['history'][0].get('failure_category') == 'test_failure' and row['history'][0].get('tests_run', 0) > 0, f'{key}: failure not reproduced')
        require(row.get('live_calls') == sum(c.get('origin') == 'live' for c in calls), f'{key}: incorrect live-call count')
        require(isinstance(row.get('heldout'), dict) and row['heldout'].get('tests_run', 0) > 0, f'{key}: missing executed held-out tests')
        if row.get('success'):
            require((row.get('heldout') or {}).get('passed') is True, f'{key}: public-only success')
        budget = settings.get('max_http_requests_per_arm')
        if budget is not None:
            require(isinstance(budget, int) and budget >= 0 and row.get('live_calls', 0) <= budget, f'{key}: exceeded live-call budget')
    # The task suite injects a scripted first completion despite using mode=live.
    # This provenance cannot be inferred from the capture's mode field alone.
    return {
        'task': trace.get('case'), 'integrity_pass': not problems,
        'integrity_errors': problems, 'completed_rows': len(rows),
        'verified_successes': sum(bool(r.get('success')) and bool((r.get('heldout') or {}).get('passed')) for r in rows),
        'first_completion_origin': 'unverified_from_artifacts',
        'natural_model_failure_proven': False,
        'comparative_superiority_proven': False,
        'warning': 'A live capture mode does not prove a natural first failure; task_suite_runner scripts its initial completion.',
    }


def evaluate_directory(folder):
    folder = Path(folder)
    reports = []
    for capture in sorted(folder.glob('*-capture.json')):
        live = capture.with_name(capture.name.replace('-capture.json', '-live.json'))
        if live.exists():
            reports.append(audit_pair(capture, live))
    return {'audit_type': 'offline_evidence_integrity', 'reports': reports}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('folders', nargs='+', type=Path)
    args = p.parse_args()
    all_reports = []
    for folder in args.folders:
        data = evaluate_directory(folder)
        all_reports.extend(data['reports'])
    print(json.dumps({'audit_type': 'offline_evidence_integrity', 'reports': all_reports}, indent=2))
    if not all_reports or any(not r['integrity_pass'] for r in all_reports):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
