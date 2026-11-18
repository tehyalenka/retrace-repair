"""Offline research report for the v18 synthetic benchmark (no provider access)."""
import argparse
import json
from collections import defaultdict
from pathlib import Path
from xml.sax.saxutils import escape

DEFAULT_ARMS = ('resample', 'feedback', 'counterfactual')
SUPPORTED_ARMS = ('resample', 'feedback', 'counterfactual', 'counterfactual_replay')
ARMS = SUPPORTED_ARMS
CATEGORIES = ('bugfix', 'feature', 'refactor', 'multifile', 'regression', 'enterprise')


def _blocked(row):
    return any(h.get('failure_stage') == 'model_request' and
               h.get('failure_category') == 'provider_error'
               for h in row.get('history', []))


def _infra(row):
    return any('Start directory is not importable' in str(h.get('output', '')) or
               'No tests discovered' in str(h.get('output', ''))
               for h in row.get('history', []))


def get_active_arms(results_dir):
    found = set()
    for p in Path(results_dir).glob("*-live.json"):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            for r in d.get("rows", []):
                if r.get("condition"):
                    found.add(r.get("condition"))
            for k in d.get("pending", {}):
                found.add(k.split(":", 1)[1])
        except Exception:
            pass
    if "counterfactual_replay" in found:
        return ('resample', 'feedback', 'counterfactual_replay')
    return ('resample', 'feedback', 'counterfactual')


def collect(results_dir, manifest_path=None):
    results_dir = Path(results_dir)
    if manifest_path is None:
        manifest_path = Path(__file__).parent / 'task_suite' / 'manifest.json'
    tasks = json.loads(Path(manifest_path).read_text())['tasks']
    active_arms = get_active_arms(results_dir)
    records = []
    for item in tasks:
        path = results_dir / (item['id'] + '-live.json')
        if not path.exists():
            for arm in active_arms:
                records.append(dict(task=item['id'], category=item['category'], arm=arm,
                                    repetition=1, status='missing', public=None, heldout=None,
                                    combined=None, calls=0, infrastructure_warning=False))
            continue
        data = json.loads(path.read_text())
        seen = set()
        reservations = data.get('request_reservations', {})
        for row in data.get('rows', []):
            arm = row['condition']
            if arm not in SUPPORTED_ARMS:
                raise ValueError('Unknown strategy: ' + str(arm))
            rep = int(row.get('repetition', 1))
            key = (rep, arm)
            if key in seen:
                raise ValueError('Duplicate completed row: ' + str(key))
            seen.add(key)
            blocked = _blocked(row)
            heldout = (row.get('heldout') or {}).get('passed')
            public = bool(row.get('success')) if not blocked else None
            hidden = bool(heldout) if heldout is not None and not blocked else None
            records.append(dict(task=item['id'], category=item['category'], arm=arm,
                                repetition=rep, status='provider_blocked' if blocked else 'completed',
                                public=public, heldout=hidden,
                                combined=bool(public and hidden) if not blocked and hidden is not None else None,
                                calls=int(row.get('live_calls', 0)),
                                http_requests=(
                                    reservations.get(row.get('key', f'{rep}:{arm}'))
                                    if row.get('key', f'{rep}:{arm}') in reservations
                                    else (row.get('request_accounting') or {}).get('http_requests')
                                ),
                                prompt_tokens=(row.get('request_accounting') or {}).get('prompt_tokens'),
                                completion_tokens=(row.get('request_accounting') or {}).get('completion_tokens'),
                                usage_reports=(row.get('request_accounting') or {}).get('usage_reports'),
                                infrastructure_warning=_infra(row)))
        for key in data.get('pending', {}):
            rep_str, arm = key.split(':', 1)
            if arm not in SUPPORTED_ARMS:
                raise ValueError('Unknown pending strategy: ' + arm)
            rep = int(rep_str)
            if (rep, arm) in seen:
                raise ValueError('Duplicate pending/completed key: ' + key)
            seen.add((rep, arm))
            records.append(dict(task=item['id'], category=item['category'], arm=arm,
                                repetition=rep, status='pending', public=None, heldout=None,
                                combined=None, calls=0,
                                http_requests=reservations.get(key),
                                prompt_tokens=None,
                                completion_tokens=None,
                                usage_reports=None,
                                infrastructure_warning=False))
        reps = int(data.get('settings', {}).get('repetitions', 1))
        for rep in range(1, reps + 1):
            for arm in active_arms:
                if (rep, arm) not in seen:
                    records.append(dict(task=item['id'], category=item['category'], arm=arm,
                                        repetition=rep, status='missing', public=None, heldout=None,
                                        combined=None, calls=0, infrastructure_warning=False))
    return records


def summarize(records):
    arms_in_records = tuple(a for a in SUPPORTED_ARMS if any(r['arm'] == a for r in records))
    if not arms_in_records:
        arms_in_records = DEFAULT_ARMS

    totals = {}
    for arm in arms_in_records:
        rows = [r for r in records if r['arm'] == arm]
        completed = [r for r in rows if r['status'] == 'completed']
        totals[arm] = {'completed': len(completed), 'pending': sum(r['status'] == 'pending' for r in rows),
                       'blocked_legacy': sum(r['status'] == 'provider_blocked' for r in rows),
                       'missing': sum(r['status'] == 'missing' for r in rows),
                       'public_pass': sum(r['public'] is True for r in completed),
                       'heldout_pass': sum(r['heldout'] is True for r in completed),
                       'combined_pass': sum(r['combined'] is True for r in completed),
                       'live_calls': sum(r['calls'] for r in rows),
                       'infrastructure_warnings': sum(r['infrastructure_warning'] for r in completed)}
    resource_usage = {}

    for arm in arms_in_records:
        rows = [r for r in records if r['arm'] == arm]

        known_http = [
            r for r in rows
            if r.get('http_requests') is not None
        ]

        observed_tokens = [
            r for r in rows
            if r.get('usage_reports') is not None
            and r.get('usage_reports') > 0
            and r.get('prompt_tokens') is not None
            and r.get('completion_tokens') is not None
        ]

        resource_usage[arm] = {
            'http_known_evaluations': len(known_http),
            'http_unknown_evaluations': len(rows) - len(known_http),
            'known_http_requests': sum(
                int(r['http_requests']) for r in known_http
            ) if known_http else None,
            'token_observed_evaluations': len(observed_tokens),
            'observed_prompt_tokens': sum(
                int(r['prompt_tokens']) for r in observed_tokens
            ) if observed_tokens else None,
            'observed_completion_tokens': sum(
                int(r['completion_tokens']) for r in observed_tokens
            ) if observed_tokens else None,
        }

    by_category = []
    for category in CATEGORIES:
        for arm in arms_in_records:
            rows = [r for r in records if r['category'] == category and r['arm'] == arm]
            if rows:
                by_category.append({'category': category, 'arm': arm,
                                    'completed': sum(r['status'] == 'completed' for r in rows),
                                    'pending': sum(r['status'] == 'pending' for r in rows),
                                    'combined_pass': sum(r['combined'] is True for r in rows)})
    by_key = defaultdict(dict)
    for r in records:
        by_key[(r['task'], r['repetition'])][r['arm']] = r
    pairs = {}
    third_arm = 'counterfactual_replay' if 'counterfactual_replay' in arms_in_records else 'counterfactual'
    pair_tuples = [('resample', 'feedback'), ('resample', third_arm), ('feedback', third_arm)]
    for a, b in pair_tuples:
        pair = {'eligible': 0, 'both_pass': 0, 'a_only': 0, 'b_only': 0, 'neither_pass': 0}
        for group in by_key.values():
            x, y = group.get(a), group.get(b)
            if not x or not y or x['status'] != 'completed' or y['status'] != 'completed':
                continue
            pair['eligible'] += 1
            xp, yp = x['combined'] is True, y['combined'] is True
            pair['both_pass' if xp and yp else 'a_only' if xp else 'b_only' if yp else 'neither_pass'] += 1
        pairs[a + '_vs_' + b] = pair
    return {'strategies': totals, 'resource_usage': resource_usage,
            'categories': by_category, 'paired': pairs,
            'scope': {'tasks': len(set(r['task'] for r in records)), 'evaluations': len(records),
                      'completed': sum(r['status'] == 'completed' for r in records),
                      'pending': sum(r['status'] == 'pending' for r in records),
                      'infrastructure_warnings': sum(r['infrastructure_warning'] for r in records)}}


def svg_chart(data, path):
    # Dependency-free static SVG; plots counts, not misleading success rates.
    arms = list(data['strategies'].keys())
    width = 780
    height = max(330, 110 + len(arms) * 65)
    colors = {'completed': '#2563eb', 'pending': '#f59e0b', 'blocked_legacy': '#ef4444', 'missing': '#9ca3af'}
    max_count = max(1, max(sum(data['strategies'][a][k] for k in colors) for a in arms))
    pieces = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
              '<rect width="100%" height="100%" fill="white"/>',
              '<text x="25" y="30" font-family="sans-serif" font-size="18" font-weight="bold">Evaluation coverage by strategy</text>']
    for idx, arm in enumerate(arms):
        y = 75 + idx * 65
        pieces.append(f'<text x="25" y="{y+18}" font-family="sans-serif" font-size="14">{escape(arm)}</text>')
        x = 170
        for key in colors:
            count = data['strategies'][arm][key]
            w = count / max_count * 540
            if count:
                pieces.append(f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="26" fill="{colors[key]}"/>')
                if w > 24:
                    pieces.append(f'<text x="{x+w/2:.1f}" y="{y+18}" text-anchor="middle" fill="white" font-family="sans-serif" font-size="12">{count}</text>')
            x += w
    x = 25
    legend_y = height - 46
    for key in colors:
        pieces.append(f'<rect x="{x}" y="{legend_y}" width="13" height="13" fill="{colors[key]}"/>')
        pieces.append(f'<text x="{x+18}" y="{legend_y+11}" font-family="sans-serif" font-size="12">{key.replace("_", " ")}</text>')
        x += 160
    pieces.append('</svg>')
    path.write_text('\n'.join(pieces), encoding='utf-8')


def markdown_report(data):
    scope = data['scope']
    arms = list(data['strategies'].keys())
    lines = ['# RETRACE: Synthetic Three-Arm Repair Benchmark', '',
             '## Evaluation status', '',
             f"This report covers {scope['tasks']} synthetic tasks and {scope['evaluations']} strategy evaluations: "
             f"{scope['completed']} completed and {scope['pending']} pending. Pending evaluations are **not** repair failures.", '',
             '| Strategy | Completed | Pending | Public pass | Heldout pass | Combined pass | Successful model calls |',
             '|---|---:|---:|---:|---:|---:|---:|']
    for arm in arms:
        r = data['strategies'][arm]
        lines.append(f"| {arm} | {r['completed']} | {r['pending']} | {r['public_pass']} | {r['heldout_pass']} | {r['combined_pass']} | {r['live_calls']} |")
    lines += ['', '![Evaluation coverage](evaluation-coverage.svg)', '',
              '## Resource usage', '',
              '| Strategy | HTTP known | HTTP unknown | Known HTTP requests | Token-observed evaluations | Observed prompt tokens | Observed completion tokens |',
              '|---|---:|---:|---:|---:|---:|---:|']

    for arm in arms:
        usage = data['resource_usage'][arm]

        def display(value):
            return 'N/A' if value is None else str(value)

        lines.append(
            f"| {arm} | "
            f"{usage['http_known_evaluations']} | "
            f"{usage['http_unknown_evaluations']} | "
            f"{display(usage['known_http_requests'])} | "
            f"{usage['token_observed_evaluations']} | "
            f"{display(usage['observed_prompt_tokens'])} | "
            f"{display(usage['observed_completion_tokens'])} |"
        )

        def display(value):
            return 'N/A' if value is None else str(value)

        lines.append(
            f"| {arm} | "
            f"{usage['http_known_evaluations']} | "
            f"{usage['http_unknown_evaluations']} | "
            f"{display(usage['known_http_requests'])} | "
            f"{usage['token_observed_evaluations']} | "
            f"{display(usage['observed_prompt_tokens'])} | "
            f"{display(usage['observed_completion_tokens'])} |"
        )

    lines += ['', 'HTTP request counts include durable reservations when available. '
              'Reservations conservatively count attempts and do not prove that every '
              'request reached the provider.', '',
              'Observed token counts are not necessarily complete totals, particularly '
              'for evaluations resumed from checkpoints. N/A means accounting data '
              'is unavailable, not zero.', '',
              '## Methodology', '',
              'The three strategies are resampling, standard failure-feedback repair, and counterfactual-guided prompting. '
              'Each task begins with a replayed deterministic failed edit. Public test feedback may guide repair; '
              'heldout verification is intended for post-repair evaluation. Fixtures are synthetic and not an external benchmark.', '',
              'Combined pass requires both public and heldout passes. Only completed evaluations are included in pass counts. '
              'Paired comparisons include a task/repetition only when both strategies completed.', '',
              '## Category breakdown', '',
              '| Category | Strategy | Completed | Pending | Combined pass |',
              '|---|---|---:|---:|---:|']
    for r in data['categories']:
        lines.append(f"| {r['category']} | {r['arm']} | {r['completed']} | {r['pending']} | {r['combined_pass']} |")
    lines += ['', '## Paired comparisons (combined pass)', '',
              '| Comparison | Eligible pairs | Both pass | First only | Second only | Neither |',
              '|---|---:|---:|---:|---:|---:|']
    for name, r in data['paired'].items():
        lines.append(f"| {name.replace('_vs_', ' vs ')} | {r['eligible']} | {r['both_pass']} | {r['a_only']} | {r['b_only']} | {r['neither_pass']} |")
    lines += ['', '## Validity and limitations', '',
              f"- {scope['infrastructure_warnings']} completed evaluations contain a recognizable test-discovery infrastructure warning. "
              'These outcomes require investigation before any performance claim.',
              '- Provider interruptions and incomplete evaluations may reduce usable paired comparisons. '
              'Do not interpret incomplete evaluations as failed repairs.',
              '- A heldout pass alongside a public failure is not counted as combined success.',
              '- Small samples, synthetic fixtures, and a deterministic replayed first failure limit generalizability.',
              '- `live_calls` counts recorded successful model responses, not necessarily all attempted provider requests.',
              '- Never include heldout test contents in model repair prompts.', '',
              '## Reproduction', '', '```bash',
              'PYTHONPATH=src:. python -m benchmarks.v18.research_report --results-dir v18-task-suite-results --output-dir v18-task-suite-results/research',
              '```', '', 'This command reads local JSON only; it does not call an LLM.', '']
    return '\n'.join(lines)


def generate(results_dir, output_dir, manifest_path=None):
    records = collect(results_dir, manifest_path)
    data = summarize(records)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / 'research-metrics.json').write_text(json.dumps(data, indent=2) + '\n')
    (output_dir / 'research-report.md').write_text(markdown_report(data))
    svg_chart(data, output_dir / 'evaluation-coverage.svg')
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results-dir', default='v18-task-suite-results')
    parser.add_argument('--output-dir', default='v18-task-suite-results/research')
    args = parser.parse_args()
    print(json.dumps(generate(args.results_dir, args.output_dir)['scope'], indent=2))


if __name__ == '__main__':
    main()
