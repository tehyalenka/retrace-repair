"""Advanced v1.1 independent-test benchmark; requires a configured LLM API."""
import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / 'src'))
from codepilot.agent import run_agent

CASES = ('bugfix', 'feature', 'refactor')

def evaluate(names, attempts, generated, output, agent=run_agent):
    tasks = json.loads((HERE / 'tasks.json').read_text(encoding='utf-8'))
    results = []
    for name in names:
        start = time.monotonic()
        try:
            verification = (HERE / 'hidden' / (name + '.py')).read_text(encoding='utf-8')
            result = agent(str(HERE / 'cases' / name), tasks[name], attempts=attempts,
                           verification=verification, generate_tests=generated)
            history = result.get('history', [])
            final = history[-1] if history else {}
            results.append({'case': name, 'success': bool(result['success']),
                            'first_attempt_passed': bool(history and history[0].get('passed')),
                            'attempts_used': len(history),
                            'independent_tests_passed': bool(final.get('verification_passed')),
                            'history': history, 'files': result.get('files', {}),
                            'elapsed_seconds': round(time.monotonic() - start, 3)})
        except Exception as exc:
            results.append({'case': name, 'success': False, 'first_attempt_passed': False,
                            'attempts_used': 0, 'independent_tests_passed': False,
                            'error': '{}: {}'.format(type(exc).__name__, exc),
                            'elapsed_seconds': round(time.monotonic() - start, 3)})
        print('{}: {}'.format(name, 'PASS' if results[-1]['success'] else 'FAIL'), flush=True)
    n = len(results)
    successes = sum(r['success'] for r in results)
    first = sum(r['first_attempt_passed'] for r in results)
    report = {'cases': results, 'summary': {'passed': successes, 'total': n,
              'first_attempt_passed': first, 'success_rate': successes/n if n else 0.0,
              'first_attempt_success_rate': first/n if n else 0.0,
              'recovered_after_failure': sum(r['success'] and not r['first_attempt_passed'] for r in results),
              'total_elapsed_seconds': round(sum(r['elapsed_seconds'] for r in results), 3)}}
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('Saved {} ({} / {} passed)'.format(output, successes, n))
    return report

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=('all',) + CASES, default='all')
    parser.add_argument('--attempts', type=int, choices=range(1,6), default=3)
    parser.add_argument('--generate-tests', action='store_true')
    parser.add_argument('--output', default='benchmark-v11-result.json')
    args = parser.parse_args()
    evaluate(CASES if args.case == 'all' else (args.case,), args.attempts, args.generate_tests, args.output)

if __name__ == '__main__':
    main()
