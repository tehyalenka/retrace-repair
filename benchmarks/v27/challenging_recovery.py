"""v2.7 multi-file benchmark; live tasks use independent hidden verification."""
import argparse
import json
from pathlib import Path
from unittest.mock import patch
import benchmarks.v18.record_replay as record_replay
import benchmarks.v22.natural_recovery as v22

HERE = Path(__file__).resolve().parent
CASES = ('pricing', 'session')
ORIGINAL_SETUP = record_replay.task_setup

def setup(mode, case, temp):
    if case not in CASES:
        raise ValueError('Unknown v2.7 case: ' + str(case))
    if mode == 'offline':
        return ORIGINAL_SETUP(mode, 'bugfix', temp)
    tasks = json.loads((HERE / 'tasks.json').read_text())
    return HERE / 'cases' / case, tasks[case], (HERE / 'hidden' / (case + '.py')).read_text()

def evaluate(**kwargs):
    with patch.object(record_replay, 'task_setup', side_effect=setup), \
         patch.object(v22, 'task_setup', side_effect=setup), \
         patch.object(v22, 'CASES', CASES):
        return v22.evaluate(capture_fn=record_replay.capture, **kwargs)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode', choices=('offline','live'), default='offline')
    p.add_argument('--cases', nargs='+', choices=CASES, default=list(CASES))
    p.add_argument('--repeats', type=int, default=1)
    p.add_argument('--attempts', type=int, default=3)
    p.add_argument('--seed', type=int, default=2026)
    p.add_argument('--cooldown', type=float, default=90)
    p.add_argument('--output', default='v27-offline.json')
    p.add_argument('--resume', action='store_true')
    a = p.parse_args()
    if a.mode == 'live' and a.output == 'v27-offline.json':
        p.error('Specify a distinct --output for live experiments')
    result = evaluate(mode=a.mode, cases=a.cases, repeats=a.repeats, attempts=a.attempts,
                      seed=a.seed, cooldown=a.cooldown, output=a.output, resume=a.resume)
    print('Status:', result['status'])
    print('Summary:', json.dumps(result['summary'], indent=2))

if __name__ == '__main__':
    main()
