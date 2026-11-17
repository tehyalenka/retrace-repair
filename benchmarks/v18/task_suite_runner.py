"""Validate self-contained fixtures and run leakage-resistant live comparisons.

Fixtures are synthetic, not independently sourced software engineering tasks.
Only public failures may be included in repair prompts; heldout runs post-repair.
Run untrusted code only in a secure sandbox; this harness is NOT a sandbox.
"""
import argparse
import hashlib
import re
import json
import shutil
import subprocess
import sys
import os
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from benchmarks.v18 import record_replay, leakage_resistant
from benchmarks.v18 import checkpointed_three_arm

ROOT = Path(__file__).parent / 'task_suite'

def tasks():
    return json.loads((ROOT/'manifest.json').read_text())['tasks']

def fixture(item, repo_dir):
    """Create an isolated task repo with its public tests discoverable.

    Heldout tests are deliberately not copied into the agent workspace.
    """
    shutil.copytree(ROOT/item['repo'], repo_dir)
    public_source = (ROOT / item['public_verifier']).read_text(encoding='utf-8')
    tests_dir = repo_dir / 'tests'
    tests_dir.mkdir(exist_ok=True)
    (tests_dir / 'test_public.py').write_text(public_source, encoding='utf-8')
    return repo_dir

def verify(repo, source):
    # Isolated subprocess with repo imports; no provider calls.
    with tempfile.TemporaryDirectory() as tmp:
        test=Path(tmp)/'test_suite_fixture.py'
        test.write_text(source,encoding='utf-8')
        env=os.environ.copy()
        env['PYTHONPATH']=str(repo)
        result=subprocess.run([sys.executable,'-m','unittest','discover','-s',tmp,
                               '-p','test_suite_fixture.py'],cwd=repo,env=env,
                              capture_output=True,text=True,timeout=15)
        # A successful exit with zero discovered tests is not verification.
        output = result.stderr + "\n" + result.stdout
        match = re.search(r"^Ran (\d+) tests? in ", output, re.MULTILINE)
        count = int(match.group(1)) if match else 0
        skipped = re.search(r"\(skipped=(\d+)\)", output)
        skipped_count = int(skipped.group(1)) if skipped else 0
        return result.returncode == 0 and count > skipped_count

def validate():
    def check(item):
        public=(ROOT/item['public_verifier']).read_text()
        heldout=(ROOT/item['heldout_verifier']).read_text()
        with tempfile.TemporaryDirectory() as tmp:
            original=fixture(item,Path(tmp)/'repo')
            bad_public=verify(original,public)
            fixed=Path(tmp)/'fixed'
            shutil.copytree(ROOT/item['solution'],fixed)
            good_public=verify(fixed,public)
            good_heldout=verify(fixed,heldout)
        return {'id':item['id'],'category':item['category'],
                        'initial_public_pass':bad_public,'solution_public_pass':good_public,
                        'solution_heldout_pass':good_heldout}
    with ThreadPoolExecutor(max_workers=8) as pool:
        return list(pool.map(check,tasks()))

def run_live(output_dir, repetitions=1, attempts=3, delay_seconds=0, max_http_requests_per_arm=None, task_id=None, category=None, task_ids=None, counterfactual_policy=None):
    if counterfactual_policy is None:
        counterfactual_policy = os.environ.get("CODEPILOT_COUNTERFACTUAL_POLICY", "counterfactual")
    output_dir=Path(output_dir);output_dir.mkdir(parents=True,exist_ok=True)
    all_rows=[]
    for item in tasks():
        if task_id is not None and item['id'] != task_id:
            continue
        if task_ids is not None and item['id'] not in task_ids:
            continue
        if category is not None and item['category'] != category:
            continue
        public=(ROOT/item['public_verifier']).read_text()
        heldout=(ROOT/item['heldout_verifier']).read_text()
        # A deterministic incorrect edit reproduces the source's known public failure.
        # Live calls are used only for subsequent repairs, as in checkpointed_three_arm.
        first=json.dumps({'reasoning_summary':'Replayed known failed implementation',
                          'edits':[{'path':p.name,'operation':'modify','content':p.read_text()}
                                   for p in sorted((ROOT/item['repo']).glob('*.py'))]})
        def setup(mode, case, temp):
            repo=fixture(item,Path(temp)/'repo')
            return repo,item['task'],public
        trace_path=output_dir/(item['id']+'-capture.json')
        report_path=output_dir/(item['id']+'-live.json')
        # Capture without provider calls, with the same deterministic failed edit for every arm.
        with patch.object(record_replay,'task_setup',side_effect=setup):
            with patch.object(record_replay.agent_module,'ask_model',return_value=first):
                trace=(json.loads(trace_path.read_text()) if trace_path.exists()
                       else record_replay.capture('live',item['id'],trace_path))
            first_attempt = trace['first_attempt']
            if (
                first_attempt.get('failure_category') != 'test_failure'
                or first_attempt.get('tests_run', 0) < 1
                or 'No tests discovered' in str(first_attempt.get('output', ''))
                or 'Start directory is not importable' in str(first_attempt.get('output', ''))
            ):
                raise ValueError(
                    'Expected a genuine public-test failure with discovered tests for '
                    + item['id']
                )
            try:
                report=checkpointed_three_arm.evaluate(trace_path,report_path,offline=False,
                           repetitions=repetitions,attempts=attempts,heldout_verification=heldout,
                              max_http_requests_per_arm=max_http_requests_per_arm,
                              counterfactual_policy=counterfactual_policy)
            except checkpointed_three_arm.ProviderBlocked as exc:
                print('PROVIDER BLOCKED on {}: {}'.format(item['id'], exc), flush=True)
                print('Existing completed results retained; rerun after quota reset.', flush=True)
                summarize(output_dir)
                return all_rows
            except checkpointed_three_arm.BenchmarkBudgetExceeded as exc:
                print('HTTP BUDGET EXHAUSTED on {}: {}'.format(item['id'], exc), flush=True)
                print('Checkpoint preserved. Inspect the budget before resuming.', flush=True)
                summarize(output_dir)
                return all_rows
        all_rows.append({'task':item['id'],'category':item['category'],
                         'arms':[{'condition':r['condition'],'public_pass':r['success'],
                                  'heldout_pass':r['heldout']['passed'],
                                  'combined_pass':bool(r['success'] and r['heldout']['passed']),
                                  'live_calls':r['live_calls']}
                                 for r in report['rows']]})
        summarize(output_dir)
        print('Completed task:',item['id'],flush=True)
        if delay_seconds:
            time.sleep(delay_seconds)
    return all_rows

def _provider_blocked(row):
    return any(h.get('failure_stage') == 'model_request' and
               h.get('failure_category') == 'provider_error'
               for h in row.get('history', []))


def migrate_legacy(output_dir):
    """Convert old provider-error rows to resumable pending calls, with backups.

    No model calls. Does not alter completed rows or already-pending keys.
    """
    output_dir = Path(output_dir)
    migrated = 0
    for item in tasks():
        path = output_dir / (item['id'] + '-live.json')
        if not path.exists():
            continue
        report = json.loads(path.read_text(encoding='utf-8'))
        blocked = [r for r in report.get('rows', []) if _provider_blocked(r)]
        if not blocked:
            continue
        keys = [r['key'] for r in blocked]
        if len(set(keys)) != len(keys):
            raise ValueError('Duplicate legacy row keys in ' + str(path))
        for row in blocked:
            key = row['key']
            if key in report.get('pending', {}):
                raise ValueError('Pending key collision in ' + str(path) + ': ' + key)
            calls = row.get('calls', [])
            if not calls or calls[0].get('origin') != 'captured_initial':
                raise ValueError('Missing initial replay call for ' + str(path) + ': ' + key)
            if any(not isinstance(c.get('request'), dict) or not isinstance(c.get('response'), str)
                   for c in calls):
                raise ValueError('Invalid replay calls in ' + str(path) + ': ' + key)
        # Preserve all successful responses; failed HTTP calls have no response to replay.
        report.setdefault('pending', {})
        for row in blocked:
            report['pending'][row['key']] = [
                {'request': c['request'], 'response': c['response']}
                for c in row['calls']
            ]
        report['rows'] = [r for r in report['rows'] if not _provider_blocked(r)]
        backup = path.with_suffix('.pre-recovery.json')
        if backup.exists():
            raise FileExistsError('Recovery backup already exists: ' + str(backup))
        shutil.copy2(path, backup)
        checkpointed_three_arm._write(path, report)
        migrated += len(blocked)
    return migrated


def summarize(output_dir):
    """Report only valid finished evaluations as completed; surface blocked legacy rows."""
    output_dir = Path(output_dir)
    summary = []
    totals = {arm: {'completed': 0, 'provider_blocked': 0, 'pending': 0,
                    'combined_pass': 0, 'public_pass': 0, 'heldout_pass': 0,
                    'live_calls': 0}
              for arm in ('resample', 'feedback', 'counterfactual', 'counterfactual_replay')}
    proof_items = []
    for item in tasks():
        path = output_dir / (item['id'] + '-live.json')
        if not path.exists():
            continue
        report = json.loads(path.read_text(encoding='utf-8'))
        rows = []
        for r in report.get('rows', []):
            arm = r['condition']
            if arm not in totals:
                totals[arm] = {'completed': 0, 'provider_blocked': 0, 'pending': 0,
                               'combined_pass': 0, 'public_pass': 0, 'heldout_pass': 0,
                               'live_calls': 0}
            blocked = _provider_blocked(r)
            heldout = r.get('heldout') or {}
            public = bool(r.get('success'))
            hidden = bool(heldout.get('passed'))
            status = 'provider_blocked' if blocked else 'completed'
            rows.append({'condition': arm, 'repetition': r.get('repetition', 1),
                         'public_pass': public, 'heldout_pass': hidden,
                         'combined_pass': public and hidden,
                         'live_calls': r.get('live_calls', 0), 'status': status})
            t = totals[arm]
            t['live_calls'] += r.get('live_calls', 0)
            if blocked:
                t['provider_blocked'] += 1
            else:
                t['completed'] += 1
                for field in ('combined_pass', 'public_pass', 'heldout_pass'):
                    t[field] += int(rows[-1][field])
        pending = list(report.get('pending', {}))
        for key in pending:
            try:
                arm = key.split(':', 1)[1]
                if arm not in totals:
                    totals[arm] = {'completed': 0, 'provider_blocked': 0, 'pending': 0,
                                   'combined_pass': 0, 'public_pass': 0, 'heldout_pass': 0,
                                   'live_calls': 0}
                totals[arm]['pending'] += 1
            except (IndexError, KeyError):
                raise ValueError('Unknown pending checkpoint key: ' + key)
        summary.append({'task': item['id'], 'category': item['category'],
                        'arms': rows, 'pending': pending})

        settings = report.get('settings', {})
        cap_path = output_dir / (item['id'] + '-capture.json')
        cap_data = json.loads(cap_path.read_text(encoding='utf-8')) if cap_path.exists() else {}
        proof_items.append({
            'task': item['id'],
            'category': item['category'],
            'repo_sha256': settings.get('repo_sha256') or cap_data.get('repo_sha256'),
            'verifier_sha256': settings.get('verifier_sha256') or cap_data.get('verifier_sha256'),
            'heldout_sha256': settings.get('heldout_sha256'),
            'trace_sha256': settings.get('trace_sha256'),
            'completed_arms': [
                {
                    'condition': r.get('condition'),
                    'repetition': r.get('repetition'),
                    'public_pass': bool(r.get('success')),
                    'heldout_pass': bool((r.get('heldout') or {}).get('passed')),
                    'combined_pass': bool(r.get('success') and (r.get('heldout') or {}).get('passed')),
                    'live_calls': r.get('live_calls', 0),
                }
                for r in report.get('rows', [])
            ],
        })

    output_dir.mkdir(parents=True, exist_ok=True)
    checkpointed_three_arm._write(output_dir / 'suite-summary.json', summary)
    checkpointed_three_arm._write(output_dir / 'suite-totals.json', totals)

    canonical_proof = json.dumps(proof_items, sort_keys=True)
    proof_digest = hashlib.sha256(canonical_proof.encode('utf-8')).hexdigest()
    proof_report = {
        'schema': 1,
        'evidence_type': 'retrace_benchmark_proof',
        'generated_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'tasks_evaluated_count': len(proof_items),
        'total_benchmark_tasks': len(tasks()),
        'tasks': proof_items,
        'suite_totals': totals,
        'proof_sha256': proof_digest,
        'all_heldout_verified': len(proof_items) > 0 and all(
            all(a['heldout_pass'] for a in p['completed_arms'] if a['public_pass'])
            for p in proof_items
        ),
    }
    checkpointed_three_arm._write(output_dir / 'benchmark-proof.json', proof_report)
    return totals


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['validate','live','summarize','recover'])
    parser.add_argument('--output-dir',default='v18-task-suite-results')
    parser.add_argument('--task',choices=[item['id'] for item in tasks()],default=None,
                        help='Run only the selected task in live mode')
    parser.add_argument('--tasks',type=str,default=None,
                        help='Comma-separated task IDs to evaluate together')
    parser.add_argument('--category',choices=['bugfix','feature','refactor','multifile','regression','enterprise'],default=None,
                        help='Run only tasks belonging to this category')
    parser.add_argument('--repetitions',type=int,default=1)
    parser.add_argument('--attempts',type=int,default=3)
    parser.add_argument('--max-http-requests-per-arm',type=int,default=None)
    parser.add_argument('--delay-seconds',type=float,default=0,help='Pause between tasks (not per request)')
    args=parser.parse_args()
    if args.delay_seconds < 0:
        parser.error('--delay-seconds must be nonnegative')
    if args.command=='recover':
        print('Recovered provider-blocked evaluations:', migrate_legacy(args.output_dir))
        print(json.dumps(summarize(args.output_dir), indent=2))
        return
    if args.command=='summarize':
        print(json.dumps(summarize(args.output_dir),indent=2))
        return
    checks=validate()
    for c in checks:
        print(c['id'], 'initial_public=',c['initial_public_pass'],
              'fixed_public=',c['solution_public_pass'],'fixed_heldout=',c['solution_heldout_pass'])
    if len(checks)!=len(tasks()) or any(c['initial_public_pass'] or not c['solution_public_pass'] or not c['solution_heldout_pass'] for c in checks):
        raise SystemExit('Fixture validation failed; live experiment blocked')
    if args.command=='live':
        task_ids = [t.strip() for t in args.tasks.split(',')] if args.tasks else None
        run_live(args.output_dir,args.repetitions,args.attempts,args.delay_seconds,
                 args.max_http_requests_per_arm,task_id=args.task,category=args.category,task_ids=task_ids)

if __name__=='__main__':
    main()
