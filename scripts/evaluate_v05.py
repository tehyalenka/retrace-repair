"""CodePilot-X v0.5: paired baseline vs verifier-guided experiment.

Place alongside evaluate_v04.py. Python 3.9 compatible.
Only execute on trusted generated code: temporary directories are NOT sandboxes.
"""
import argparse
import importlib.util
import json
import statistics
import tempfile
import time
from pathlib import Path

from codepilot.agent import ask_model, run_agent

SPEC = importlib.util.spec_from_file_location('v04_benchmark', str(Path(__file__).with_name('evaluate_v04.py')))
v04 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(v04)


def generate_verifier(instruction, initial_source, module):
    """Generate independent task-derived assertions, without exposing hidden checks."""
    prompt = (
        'Create 4 to 8 Python assert statements to check the task below. '
        'Use the original public function names, include normal and edge cases. '
        'Return ONLY JSON: {"assertions": ["assert ...", ...]}. '
        'Each string must be one Python statement on one line; do not import modules, '
        'write files, or use loops. No markdown.\n'
        'TASK:\n' + instruction + '\nORIGINAL MODULE ' + module + ':\n' + initial_source
    )
    raw = ask_model([{'role': 'user', 'content': prompt}])
    if raw.strip().startswith('```'):
        raw = raw.strip().split('\n', 1)[1].rsplit('```', 1)[0]
    data = json.loads(raw)
    assertions = data['assertions']
    if not isinstance(assertions, list) or not 4 <= len(assertions) <= 8:
        raise ValueError('Verifier must return 4-8 assertions')
    for line in assertions:
        if not isinstance(line, str) or '\n' in line or not line.lstrip().startswith('assert '):
            raise ValueError('Verifier returned unsupported statement')
        compile(line, '<generated-verifier>', 'exec')
    return assertions


def agent_once(module, source, instruction, attempts):
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / (module + '.py')).write_text(source, encoding='utf-8')
        tests = root / 'tests'
        tests.mkdir()
        (tests / 'test_smoke.py').write_text(
            'import unittest\nclass Smoke(unittest.TestCase):\n'
            '    def test_smoke(self): self.assertTrue(True)\n', encoding='utf-8'
        )
        response = run_agent(str(root), instruction, attempts=attempts)
        return response, response.get('files', {}).get(module + '.py')


def run_case(case, attempts, retries):
    task_id, module, source, instruction, hidden = case
    started = time.monotonic()
    result = {'id': task_id, 'task': instruction}
    try:
        baseline, baseline_source = agent_once(module, source, instruction, attempts)
        base_ok, base_error = v04.check(baseline_source, module, hidden) if baseline_source is not None else (False, 'No source')
        result['baseline'] = {'hidden_pass': base_ok, 'error': base_error,
                              'attempts': len(baseline.get('history', []))}
        # Generate verifier AFTER baseline, without seeing hidden tests or baseline results.
        checks = generate_verifier(instruction, source, module)
        result['generated_verifier'] = checks
        current_source = baseline_source
        verified, feedback = v04.check(current_source, module, checks) if current_source is not None else (False, 'No source')
        result['verifier_initial_pass'] = verified
        result['verification_retries'] = 0
        while not verified and result['verification_retries'] < retries:
            # New attempt starts from the original repo, with feedback appended to task.
            # Never include hidden evaluator results in the feedback.
            retry_instruction = (instruction + '\nThe previous proposed change failed these '
                                 'independently generated checks:\n' + feedback[-1800:] +
                                 '\nFix the original task and preserve the function API.')
            retried, proposed = agent_once(module, source, retry_instruction, attempts)
            result['verification_retries'] += 1
            if proposed is None:
                feedback = 'Agent returned no edited source'
                continue
            current_source = proposed
            verified, feedback = v04.check(current_source, module, checks)
        final_ok, final_error = v04.check(current_source, module, hidden) if current_source is not None else (False, 'No source')
        result['verification_aware'] = {'hidden_pass': final_ok, 'error': final_error,
                                        'generated_checks_pass': verified}
    except Exception as exc:
        result['error'] = str(exc)[:1200]
    result['elapsed_seconds'] = round(time.monotonic() - started, 3)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=5)
    parser.add_argument('--attempts', type=int, default=1)
    parser.add_argument('--verification-retries', type=int, default=1)
    parser.add_argument('--output', default='benchmark-v05.json')
    args = parser.parse_args()
    if not 1 <= args.limit <= len(v04.TASKS) or not 1 <= args.attempts <= 5 or not 0 <= args.verification_retries <= 3:
        parser.error('Invalid limit, attempts, or verification-retries')
    results = []
    for case in v04.TASKS[:args.limit]:
        r = run_case(case, args.attempts, args.verification_retries)
        results.append(r)
        print('{}: baseline={} verified={}{}'.format(
            r['id'], r.get('baseline', {}).get('hidden_pass'),
            r.get('verification_aware', {}).get('hidden_pass'),
            ' ERROR=' + r['error'] if 'error' in r else ''), flush=True)
    valid = [r for r in results if 'baseline' in r and 'verification_aware' in r]
    report = {
        'benchmark': 'CodePilot-X v0.5 verifier-guided prototype',
        'completed_pairs': len(valid), 'requested_pairs': len(results),
        'baseline_success_rate': (sum(r['baseline']['hidden_pass'] for r in valid) / len(valid)) if valid else None,
        'verification_aware_success_rate': (sum(r['verification_aware']['hidden_pass'] for r in valid) / len(valid)) if valid else None,
        'mean_seconds_per_pair': statistics.mean(r['elapsed_seconds'] for r in results),
        'results': results,
        'limitations': [
            'Synthetic single-file tasks from v0.4; likely ceiling effect',
            'Generated verifier assertions are not independently validated and may be wrong',
            'Verifier is an external experiment wrapper, not yet integrated into run_agent',
            'Only task instructions and original code are shown to verifier; hidden tests remain evaluator-only',
            'Generated code and verifier statements execute locally without a security sandbox',
            'Single trial per task, no randomization, uncertainty estimate, or token-cost tracking'
        ]
    }
    Path(args.output).write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('Saved {}'.format(args.output))


if __name__ == '__main__':
    main()