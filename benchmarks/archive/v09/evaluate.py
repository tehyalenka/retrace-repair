"""Run three independent-test benchmarks. Live Groq API calls incur quota usage."""
import argparse
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / 'src'))
from codepilot.agent import run_agent


def evaluate(names, attempts, generated, output):
    tasks = json.loads((HERE / 'tasks.json').read_text(encoding='utf-8'))
    results = []
    for name in names:
        start = time.monotonic()
        verification = (HERE / 'hidden' / (name + '.py')).read_text(encoding='utf-8')
        try:
            result = run_agent(str(HERE / 'cases' / name), tasks[name],
                               attempts=attempts, verification=verification,
                               generate_tests=generated)
            history = result['history']
            final = history[-1] if history else {}
            results.append({'case': name, 'success': result['success'],
                            'first_attempt_passed': bool(history and history[0]['passed']),
                            'attempts_used': len(history),
                            'independent_tests_passed': final.get('verification_passed', False),
                            'history': history, 'files': result.get('files', {}),
                            'elapsed_seconds': round(time.monotonic() - start, 3)})
        except Exception as exc:
            results.append({'case': name, 'success': False,
                            'error': '{}: {}'.format(type(exc).__name__, exc),
                            'elapsed_seconds': round(time.monotonic() - start, 3)})
        print('{}: {}'.format(name, 'PASS' if results[-1]['success'] else 'FAIL'), flush=True)
    passed = sum(bool(r['success']) for r in results)
    first_passed = sum(bool(r.get('first_attempt_passed')) for r in results)
    total = len(results)
    report = {'cases': results,
              'summary': {'passed': passed, 'total': total,
                          'first_attempt_passed': first_passed,
                          'success_rate': passed / total if total else 0.0,
                          'first_attempt_success_rate': first_passed / total if total else 0.0,
                          'total_elapsed_seconds': round(sum(r['elapsed_seconds'] for r in results), 3)}}
    Path(output).write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('Saved {} ({} / {} passed)'.format(output, report['summary']['passed'], len(results)))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=['all', 'bugfix', 'feature', 'refactor'], default='all')
    parser.add_argument('--attempts', type=int, choices=range(1, 6), default=3)
    parser.add_argument('--generate-tests', action='store_true')
    parser.add_argument('--output', default='benchmark-v09-result.json')
    args = parser.parse_args()
    names = ['bugfix', 'feature', 'refactor'] if args.case == 'all' else [args.case]
    evaluate(names, args.attempts, args.generate_tests, args.output)


if __name__ == '__main__':
    main()
