"""Resumable, rate-limit-aware seeded repair trials; never count HTTP 429 as code failure."""
import argparse
import json
import os
import random
import re
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from benchmarks.v19.seeded_repair import SEEDS, run_case
from benchmarks.v20.rigorous_repair import summarize


def jobs_for(names, repeats, seed):
    rng = random.Random(seed)
    jobs = [(case, trial) for trial in range(1, repeats + 1) for case in names]
    rng.shuffle(jobs)
    result = []
    for case, trial in jobs:
        order = ('resample', 'feedback') if (trial + names.index(case)) % 2 else ('feedback', 'resample')
        result.extend((case, trial, condition) for condition in order)
    return result


def save_atomic(path, report):
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Atomic replace prevents partial JSON if interrupted mid-write.
    fd, temp = tempfile.mkstemp(prefix='.' + dest.name + '.', dir=str(dest.parent))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(report, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, dest)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def row_for(report, case, trial, condition):
    for item in report['cases']:
        if item['case'] == case and item['trial'] == trial:
            for row in item['rows']:
                if row['condition'] == condition:
                    return row
    return None


def provider_error(row):
    return bool(row.get('provider_failure'))


def evaluate(mode='offline', cases=None, repeats=2, attempts=3, seed=2026,
             output='v21-results.json', resume=False, cooldown=15.0,
             stop_on_rate_limit=True, runner=run_case, sleeper=time.sleep):
    if mode not in ('offline', 'live') or repeats < 1 or not 2 <= attempts <= 5 or cooldown < 0:
        raise ValueError('Invalid mode, repeats, attempts or cooldown')
    names = list(cases) if cases is not None else sorted(SEEDS)
    if not names or len(set(names)) != len(names) or not set(names).issubset(SEEDS):
        raise ValueError('Cases must be unique known cases')
    config = {'mode': mode, 'cases_selected': names, 'repeats': repeats,
              'attempts': attempts, 'random_seed': seed}
    dest = Path(output)
    if resume and dest.exists():
        report = json.loads(dest.read_text(encoding='utf-8'))
        if any(report.get(key) != value for key, value in config.items()):
            raise ValueError('Cannot resume: benchmark configuration differs from saved report')
    else:
        if dest.exists():
            raise FileExistsError('Output already exists; use --resume or a different --output')
        report = {'schema': 3, 'evaluation': 'seeded_failure_resumable',
                  'created_utc': datetime.now(timezone.utc).isoformat(), **config,
                  'cases': [], 'errors': [], 'summary': {}, 'status': 'running',
                  'limitations': ['Seeded defects are not naturally model-generated',
                                  'Offline repairs are scripted',
                                  'Rate limits cause missing outcomes',
                                  'Small synthetic benchmark cannot prove feedback superiority']}
    jobs = jobs_for(names, repeats, seed)
    def persist():
        report['summary'] = summarize(report['cases'])
        report['updated_utc'] = datetime.now(timezone.utc).isoformat()
        save_atomic(dest, report)
    persist()
    attempted_live = False
    for case, trial, condition in jobs:
        previous = row_for(report, case, trial, condition)
        if previous is not None and not provider_error(previous):
            continue
        # Retry rate-limited arms only on an explicit resumed invocation.
        if previous is not None and not resume:
            continue
        if mode == 'live' and attempted_live and cooldown:
            sleeper(cooldown)
        if mode == 'live':
            attempted_live = True
        try:
            result = runner(case, offline=(mode == 'offline'), attempts=attempts,
                            condition_order=(condition,))
            row = result['rows'][0]
            if row['condition'] != condition:
                raise ValueError('Runner returned wrong condition')
            existing = next((item for item in report['cases'] if item['case'] == case and item['trial'] == trial), None)
            if existing is None:
                existing = {k: v for k, v in result.items() if k != 'rows'}
                existing.update(trial=trial, condition_order=list(
                    ('resample', 'feedback') if (trial + names.index(case)) % 2 else ('feedback', 'resample')),
                    rows=[])
                report['cases'].append(existing)
            existing['rows'] = [r for r in existing['rows'] if r['condition'] != condition] + [row]
            print('{} trial {} {}: {}'.format(case, trial, condition,
                  'PROVIDER_FAILURE' if provider_error(row) else 'PASS' if row['success'] else 'FAIL'), flush=True)
            if provider_error(row) and stop_on_rate_limit and any(
                re.search(r'HTTP\s+429\b', h.get('output', ''), re.I) for h in row.get('history', [])):
                report['status'] = 'paused_rate_limit'
                persist()
                return report
        except Exception as exc:
            report['errors'].append({'case': case, 'trial': trial, 'condition': condition,
                                     'error_type': type(exc).__name__, 'message': str(exc)[:300]})
            print('{} trial {} {}: ERROR {}'.format(case, trial, condition, type(exc).__name__), flush=True)
        finally:
            persist()
    report['status'] = 'complete' if all(
        row_for(report, *job) is not None and not provider_error(row_for(report, *job))
        for job in jobs) else 'incomplete'
    persist()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('offline', 'live'), default='offline')
    parser.add_argument('--cases', nargs='+', choices=sorted(SEEDS), default=sorted(SEEDS))
    parser.add_argument('--repeats', type=int, default=2)
    parser.add_argument('--attempts', type=int, default=3)
    parser.add_argument('--seed', type=int, default=2026)
    parser.add_argument('--output', default='v21-results.json')
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--cooldown', type=float, default=15.0)
    parser.add_argument('--continue-on-429', action='store_true')
    args = parser.parse_args()
    report = evaluate(mode=args.mode, cases=args.cases, repeats=args.repeats,
                      attempts=args.attempts, seed=args.seed, output=args.output,
                      resume=args.resume, cooldown=args.cooldown,
                      stop_on_rate_limit=not args.continue_on_429)
    print('Status:', report['status'])
    print('Summary:', json.dumps(report['summary'], indent=2))
    print('Saved:', args.output)

if __name__ == '__main__':
    main()
