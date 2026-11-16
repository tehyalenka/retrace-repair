"""CodePilot-X v0.5.1: controlled fault detection and repair pilot.

Run only on trusted source. Temporary directories are NOT security sandboxes.
Place beside evaluate_v04.py. Requires installed codepilot package and Groq key.
"""
import argparse
import importlib.util
import json
import statistics
import tempfile
import time
from pathlib import Path

from codepilot.agent import run_agent

spec = importlib.util.spec_from_file_location('v04', str(Path(__file__).with_name('evaluate_v04.py')))
v04 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v04)

# Explicitly reviewed task-aware checks, separate from v04 withheld tests.
# A structured representation supports expected exceptions without free-form LLM code.
CHECKS = {
    'casefold': [
        {'call': 'login("ADMIN", "secret")', 'equals': True},
        {'call': 'login("AdMiN", "secret")', 'equals': True},
        {'call': 'login("admin", "SECRET")', 'equals': False},
    ],
    'division': [
        {'call': 'divide(7, 0)', 'equals': None},
        {'call': 'divide(7, 2)', 'equals': 3.5},
        {'call': 'divide(-8, 2)', 'equals': -4},
    ],
    'stable_unique': [
        {'call': 'unique([2, 1, 2, 3])', 'equals': [2, 1, 3]},
        {'call': 'unique([])', 'equals': []},
        {'call': 'unique(["a", "b", "a"])', 'equals': ['a', 'b']},
    ],
    'palindrome': [
        {'call': 'palindrome("A man, a plan, a canal: Panama!")', 'equals': True},
        {'call': 'palindrome("hello")', 'equals': False},
        {'call': 'palindrome("RaceCar")', 'equals': True},
    ],
    'clamp': [
        {'call': 'clamp(-1, 0, 5)', 'equals': 0},
        {'call': 'clamp(9, 0, 5)', 'equals': 5},
        {'call': 'clamp(2, 5, 1)', 'raises': 'ValueError'},
    ],
}


def render_checks(specs):
    """Compile a limited, reviewed schema into runnable Python assertions."""
    lines = []
    for idx, item in enumerate(specs):
        call = item['call']
        # Calls are checked against the fixed local review list, not arbitrary LLM output.
        if ('equals' in item) == ('raises' in item):
            raise ValueError('Exactly one of equals/raises required')
        if 'equals' in item:
            lines.append('assert {} == {!r}, "check {} failed"'.format(call, item['equals'], idx))
        else:
            exc = item['raises']
            if exc not in ('ValueError', 'TypeError', 'ZeroDivisionError', 'IndexError'):
                raise ValueError('Unsupported exception type')
            lines.append('try:\n {}\nexcept {}:\n pass\nelse:\n raise AssertionError("check {} expected {}")'.format(call, exc, idx, exc))
    return lines


def agent_once(module, source, instruction, attempts):
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / (module + '.py')).write_text(source, encoding='utf-8')
        (root / 'tests').mkdir()
        (root / 'tests' / 'test_smoke.py').write_text(
            'import unittest\nclass Smoke(unittest.TestCase):\n def test_smoke(self): self.assertTrue(True)\n', encoding='utf-8')
        response = run_agent(str(root), instruction, attempts=attempts)
        return response, response.get('files', {}).get(module + '.py')


def run_case(case, attempts, retries):
    task_id, module, faulty_source, instruction, hidden = case
    checks = render_checks(CHECKS[task_id])
    started = time.monotonic()
    record = {'id': task_id, 'faulty_source': faulty_source, 'verifier_spec': CHECKS[task_id]}
    # Confirm that the known faulty seed is actually detected before involving an LLM.
    detected, initial_error = v04.check(faulty_source, module, checks)
    record['fault_detected'] = not detected
    record['initial_verifier_feedback'] = initial_error
    if detected:
        record['error'] = 'Seed unexpectedly passed verification; cannot test recovery'
    else:
        try:
            # No hidden checks or hidden results are provided to the agent.
            prompt = (instruction + '\nTask-aware verification failed on the current code:\n' +
                      initial_error[-1500:] + '\nFix the implementation while preserving its public API.')
            latest = faulty_source
            record['repair_attempts'] = 0
            for _ in range(retries):
                response, proposed = agent_once(module, faulty_source, prompt, attempts)
                record['repair_attempts'] += 1
                if proposed is None:
                    prompt += '\nThe agent did not return the target file. Please edit it.'
                    continue
                latest = proposed
                verified, feedback = v04.check(latest, module, checks)
                record['verifier_pass'] = verified
                record['verifier_feedback'] = feedback
                if verified:
                    break
                prompt = (instruction + '\nThe proposed implementation failed task-aware checks:\n' +
                          feedback[-1500:] + '\nRepair the code and preserve the public API.')
            record['hidden_pass'], record['hidden_feedback'] = v04.check(latest, module, hidden)
            record['final_source'] = latest
        except Exception as exc:
            record['error'] = str(exc)[:1000]
    record['elapsed_seconds'] = round(time.monotonic() - started, 3)
    return record


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--limit', type=int, default=5)
    p.add_argument('--attempts', type=int, default=1)
    p.add_argument('--repair-retries', type=int, default=1)
    p.add_argument('--output', default='benchmark-v051.json')
    args = p.parse_args()
    if not 1 <= args.limit <= 5 or not 1 <= args.attempts <= 5 or not 0 <= args.repair_retries <= 3:
        p.error('limit must be 1-5, attempts 1-5, repair-retries 0-3')
    results = []
    for case in v04.TASKS[:args.limit]:
        if case[0] not in CHECKS:
            p.error('Unexpected task order in v04: {}'.format(case[0]))
        result = run_case(case, args.attempts, args.repair_retries)
        results.append(result)
        print('{}: fault_detected={} verifier_pass={} hidden_pass={}{}'.format(
            result['id'], result['fault_detected'], result.get('verifier_pass'),
            result.get('hidden_pass'), ' ERROR=' + result['error'] if 'error' in result else ''), flush=True)
    completed = [r for r in results if 'hidden_pass' in r]
    report = {
        'benchmark': 'CodePilot-X v0.5.1 controlled fault-injection pilot',
        'task_count': len(results),
        'fault_detection_rate': sum(r['fault_detected'] for r in results) / len(results),
        'completed_repairs': len(completed),
        'hidden_success_rate_on_completed_repairs': (
            sum(r['hidden_pass'] for r in completed) / len(completed) if completed else None),
        'mean_seconds': statistics.mean(r['elapsed_seconds'] for r in results),
        'results': results,
        'limitations': [
            'Uses reviewed, hand-authored verification cases, not LLM-generated verifier tests',
            'The faulty seeds are original toy implementations, not naturally occurring agent failures',
            'Single-file synthetic tasks; no claim of improvement over baseline',
            'Executes generated Python code locally without sandbox isolation',
        ],
    }
    Path(args.output).write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('Saved {}'.format(args.output))


if __name__ == '__main__':
    main()
