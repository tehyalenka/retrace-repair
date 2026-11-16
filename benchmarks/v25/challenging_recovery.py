"""v2.5: audited checkout instructions, original independent verifiers."""
import argparse
import json
from pathlib import Path
from unittest.mock import patch

import benchmarks.v18.record_replay as record_replay
import benchmarks.v22.natural_recovery as v22

HERE = Path(__file__).resolve().parent
V23 = HERE.parent / 'v23'
CASES = ('checkout', 'permissions', 'eventlog')
ORIGINAL_SETUP = record_replay.task_setup


def setup(mode, case, temp):
    if mode == 'offline':
        return ORIGINAL_SETUP(mode, 'bugfix', temp)
    tasks = json.loads((HERE / 'tasks.json').read_text())
    if case not in CASES or case not in tasks:
        raise ValueError('Unknown v2.5 case: ' + str(case))
    return V23 / 'cases' / case, tasks[case], (V23 / 'hidden' / (case + '.py')).read_text()


def evaluate(**kwargs):
    with patch.object(record_replay, 'task_setup', side_effect=setup), \
         patch.object(v22, 'task_setup', side_effect=setup), \
         patch.object(v22, 'CASES', CASES):
        return v22.evaluate(capture_fn=record_replay.capture, **kwargs)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode', choices=('offline', 'live'), default='offline')
    p.add_argument('--cases', nargs='+', choices=CASES, default=list(CASES))
    p.add_argument('--repeats', type=int, default=1)
    p.add_argument('--attempts', type=int, default=3)
    p.add_argument('--seed', type=int, default=2026)
    p.add_argument('--cooldown', type=float, default=90)
    p.add_argument('--output', default='v25-offline.json')
    p.add_argument('--resume', action='store_true')
    a = p.parse_args()
    if a.mode == 'live' and a.output == 'v25-offline.json':
        p.error('For live experiments, specify a new --output path (for example v25-live.json)')
    report = evaluate(mode=a.mode, cases=a.cases, repeats=a.repeats,
                      attempts=a.attempts, seed=a.seed, cooldown=a.cooldown,
                      output=a.output, resume=a.resume)
    print('Status:', report['status'])
    print('Summary:', json.dumps(report['summary'], indent=2))


if __name__ == '__main__':
    main()
