"""v2.2: resumable, naturally generated first attempts and paired recovery.

Live mode calls the configured model; offline mode uses v1.8 scripted fixtures
ONLY for harness validation. Traces contain prompts/source; keep them private.
"""
import argparse
import hashlib
import json
import random
import re
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from benchmarks.v18.record_replay import capture, task_setup, fingerprint
from benchmarks.v19.seeded_repair import safe_feedback
from benchmarks.v21.reliable_repair import save_atomic
import codepilot.agent as agent

CASES = ('bugfix', 'feature', 'refactor')
CONDITIONS = ('resample', 'feedback')


def utc():
    return datetime.now(timezone.utc).isoformat()


def rate_limited(history):
    return any(re.search(r'HTTP\s+429\b', h.get('output', ''), re.I) for h in history)


def run_arm(trace, condition, attempts=3, offline=False, prior=None, checkpoint=None):
    if trace['mode'] == 'live' and offline:
        raise ValueError('Cannot use scripted offline repairs on live captures')
    if trace['first_attempt']['failure_category'] != 'test_failure':
        raise ValueError('Only genuine test failures qualify for paired repair')
    first = trace['calls'][0]['response']
    # Replay completed responses from an interrupted arm, without another API call.
    cached = [c['response'] for c in (prior or {}).get('model_calls', [])[1:]
              if c.get('origin') in ('fresh_model_completion', 'replayed_saved_completion')
              and isinstance(c.get('response'), str)]
    with tempfile.TemporaryDirectory() as temp:
        repo, task, verifier = task_setup(trace['mode'], trace['case'], temp)
        if fingerprint(repo) != trace['repo_sha256'] or task != trace['task']:
            raise ValueError('Repository/task changed since capture')
        if hashlib.sha256(verifier.encode()).hexdigest() != trace['verifier_sha256']:
            raise ValueError('Verifier changed since capture')
        real_ask = agent.ask_model
        calls = []
        def ask(messages, **kwargs):
            if not calls:
                response, origin = first, 'replayed_natural_failure'
            elif len(calls) - 1 < len(cached):
                response, origin = cached[len(calls) - 1], 'replayed_saved_completion'
            elif offline:
                from benchmarks.v16.repair_experiment import _edit
                response, origin = _edit('def double(x):\n    return 2*x\n'), 'scripted_continuation'
            else:
                response, origin = real_ask(messages, **kwargs), 'fresh_model_completion'
            calls.append({'origin': origin, 'response': response,
                          'feedback_message_present': any('Tests/validation failed:' in m.get('content', '') for m in messages)})
            if origin == 'fresh_model_completion' and checkpoint is not None:
                # Save a completed response before the next operation can fail.
                checkpoint({'condition': condition, 'success': False, 'history': [],
                            'model_calls': [dict(c) for c in calls],
                            'fresh_model_calls': sum(c['origin'] in ('fresh_model_completion', 'replayed_saved_completion') for c in calls),
                            'replayed_saved_calls': sum(c['origin'] == 'replayed_saved_completion' for c in calls),
                            'provider_failure': True, 'checkpoint_incomplete': True})
            return response
        with patch.object(agent, 'ask_model', side_effect=ask), patch.object(agent, '_repair_feedback', side_effect=safe_feedback):
            result = agent.run_agent(repo, task, attempts=attempts, verification=verifier,
                                     repair_feedback=(condition == 'feedback'))
        history = result.get('history', [])
        if not history or history[0].get('failure_category') != 'test_failure':
            raise ValueError('Natural failure not reproduced in replay')
        return {'condition': condition, 'success': result['success'], 'history': history,
                'model_calls': calls, 'fresh_model_calls': sum(c['origin'] in ('fresh_model_completion', 'replayed_saved_completion') for c in calls),
                'replayed_saved_calls': sum(c['origin'] == 'replayed_saved_completion' for c in calls),
                'provider_failure': any(h.get('failure_category') == 'provider_error' for h in history)}


def evaluate(mode='offline', cases=CASES, repeats=2, attempts=3, seed=2026,
             output='v22-natural-results.json', resume=False, cooldown=90,
             capture_fn=capture, arm_fn=run_arm, sleeper=time.sleep):
    cases = tuple(cases)
    if mode not in ('offline', 'live') or not cases or len(set(cases)) != len(cases) or not set(cases).issubset(CASES):
        raise ValueError('Invalid mode or cases')
    if repeats < 1 or attempts < 2 or attempts > 5 or cooldown < 0:
        raise ValueError('Invalid repeats, attempts or cooldown')
    config = dict(mode=mode, cases_selected=list(cases), repeats=repeats, attempts=attempts, random_seed=seed)
    dest = Path(output)
    traces = dest.parent / (dest.stem + '-traces')
    if resume and dest.exists():
        report = json.loads(dest.read_text())
        if any(report.get(k) != v for k, v in config.items()):
            raise ValueError('Cannot resume: configuration differs')
    else:
        if dest.exists():
            raise FileExistsError('Output exists: use --resume')
        report = {'schema': 1, 'evaluation': 'natural_failure_recovery', 'created_utc': utc(),
                  **config, 'runs': [], 'status': 'running', 'errors': [],
                  'limitations': ['Only naturally observed test failures are paired',
                                  'Offline repairs are scripted, not LLM evidence',
                                  'Small samples cannot establish feedback advantage',
                                  'Traces contain prompts and source code; do not publish unreviewed']}
    jobs = [(case, trial) for trial in range(1, repeats+1) for case in cases]
    random.Random(seed).shuffle(jobs)
    def persist():
        runs = report['runs']
        report['summary'] = {
            'captures': len([r for r in runs if r.get('capture_status') in ('passed', 'failed_tests')]),
            'first_attempt_passes': sum(r.get('capture_status') == 'passed' for r in runs),
            'natural_test_failures': sum(r.get('capture_status') == 'failed_tests' for r in runs),
            'provider_capture_failures': sum(r.get('capture_status') == 'provider_error' for r in runs),
            'conditions': {c: {'completed': sum(c in r.get('arms', {}) and not r['arms'][c].get('provider_failure') and not r['arms'][c].get('checkpoint_incomplete') for r in runs),
                               'successful_repairs': sum(r.get('arms', {}).get(c, {}).get('success', False) for r in runs)}
                           for c in CONDITIONS}}
        report['updated_utc'] = utc()
        save_atomic(dest, report)
    persist()
    attempted_live = False
    for case, trial in jobs:
        record = next((r for r in report['runs'] if r['case'] == case and r['trial'] == trial), None)
        if record is None:
            record = {'case': case, 'trial': trial, 'arms': {}}
            report['runs'].append(record)
        trace_path = traces / ('{}-{}.json'.format(case, trial))
        if record.get('capture_status') not in ('passed', 'failed_tests'):
            if mode == 'live' and attempted_live and cooldown:
                sleeper(cooldown)
            attempted_live |= mode == 'live'
            try:
                trace_path.parent.mkdir(parents=True, exist_ok=True)
                trace = capture_fn(mode, case, str(trace_path))
                first = trace.get('first_attempt') or {}
                if trace.get('capture_success'):
                    record['capture_status'] = 'passed'
                elif first.get('failure_category') == 'test_failure' and trace.get('calls', [{}])[0].get('response'):
                    record['capture_status'] = 'failed_tests'
                elif first.get('failure_category') == 'provider_error' or any('error' in c for c in trace.get('calls', [])):
                    record['capture_status'] = 'provider_error'
                else:
                    record['capture_status'] = 'other_failure'
                record['first_attempt'] = first
                record['trace_path'] = str(trace_path)
            except Exception as exc:
                record['capture_status'] = 'capture_error'
                report['errors'].append({'case': case, 'trial': trial, 'stage': 'capture', 'error': str(exc)[:300]})
            persist()
            if record['capture_status'] == 'provider_error' and rate_limited([record.get('first_attempt') or {}]):
                report['status'] = 'paused_rate_limit'
                persist()
                return report
        if record['capture_status'] != 'failed_tests':
            continue
        if not trace_path.exists():
            raise FileNotFoundError('Missing saved capture trace: ' + str(trace_path))
        trace = json.loads(trace_path.read_text())
        order = CONDITIONS if trial % 2 else CONDITIONS[::-1]
        for condition in order:
            old = record['arms'].get(condition)
            if old is not None and not old.get('provider_failure') and not old.get('checkpoint_incomplete'):
                continue
            if mode == 'live' and attempted_live and cooldown:
                sleeper(cooldown)
            attempted_live |= mode == 'live'
            try:
                if arm_fn is run_arm:
                    def checkpoint(partial):
                        record['arms'][condition] = partial
                        persist()
                    row = arm_fn(trace, condition, attempts=attempts, offline=(mode == 'offline'),
                                 prior=old if old and (old.get('provider_failure') or old.get('checkpoint_incomplete')) else None,
                                 checkpoint=checkpoint)
                else:
                    row = arm_fn(trace, condition, attempts=attempts, offline=(mode == 'offline'))
                record['arms'][condition] = row
                print(case, trial, condition, 'PASS' if row['success'] else 'PROVIDER' if row['provider_failure'] else 'FAIL', flush=True)
                persist()
                if row['provider_failure'] and rate_limited(row['history']):
                    report['status'] = 'paused_rate_limit'
                    persist()
                    return report
            except Exception as exc:
                report['errors'].append({'case': case, 'trial': trial, 'condition': condition, 'error': str(exc)[:300]})
                persist()
    report['status'] = 'complete' if all(
        (r := next((x for x in report['runs'] if x['case'] == case and x['trial'] == trial), {})).get('capture_status') == 'passed'
        or (r.get('capture_status') == 'failed_tests' and all(c in r['arms'] and not r['arms'][c].get('provider_failure') and not r['arms'][c].get('checkpoint_incomplete') for c in CONDITIONS))
        for case, trial in jobs) else 'incomplete'
    persist()
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode', choices=('offline', 'live'), default='offline')
    p.add_argument('--cases', nargs='+', choices=CASES, default=list(CASES))
    p.add_argument('--repeats', type=int, default=2)
    p.add_argument('--attempts', type=int, default=3)
    p.add_argument('--seed', type=int, default=2026)
    p.add_argument('--output', default='v22-natural-results.json')
    p.add_argument('--resume', action='store_true')
    p.add_argument('--cooldown', type=float, default=90)
    args = p.parse_args()
    result = evaluate(mode=args.mode, cases=args.cases, repeats=args.repeats,
                      attempts=args.attempts, seed=args.seed, output=args.output,
                      resume=args.resume, cooldown=args.cooldown)
    print('Status:', result['status'])
    print('Summary:', json.dumps(result['summary'], indent=2))

if __name__ == '__main__':
    main()
