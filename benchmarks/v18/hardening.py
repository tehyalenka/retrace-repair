"""Offline benchmark hardening. Trusted fixtures only; NOT a sandbox.

No provider requests, agent features, or experimental arms are added.
"""
import argparse
import ast
import json
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from benchmarks.v18.task_suite_runner import ROOT, tasks, verify


class ReplaceFirstReturn(ast.NodeTransformer):
    """Deterministic semantic fault: replace the first return value with None."""
    def __init__(self):
        self.changed = False

    def visit_Return(self, node):
        if not self.changed and node.value is not None:
            self.changed = True
            return ast.copy_location(ast.Return(value=ast.Constant(value=None)), node)
        return node


def mutate_solution(repo):
    """Apply one syntactically valid semantic mutation to a copied solution."""
    for path in sorted(repo.rglob('*.py')):
        if any(part in ('tests', '__pycache__') for part in path.parts):
            continue
        original = path.read_text(encoding='utf-8')
        tree = ast.parse(original, filename=str(path))
        transformer = ReplaceFirstReturn()
        tree = transformer.visit(tree)
        if transformer.changed:
            ast.fix_missing_locations(tree)
            path.write_text(ast.unparse(tree) + '\n', encoding='utf-8')
            return str(path.relative_to(repo))
    raise ValueError('No return statement available to mutate: ' + str(repo))


def audit_task(item):
    """Evaluate whether independent public/heldout tests kill a semantic mutant."""
    public = (ROOT / item['public_verifier']).read_text(encoding='utf-8')
    heldout = (ROOT / item['heldout_verifier']).read_text(encoding='utf-8')
    with tempfile.TemporaryDirectory(prefix='retrace-hardening-') as temp:
        repo = Path(temp) / 'solution'
        shutil.copytree(ROOT / item['solution'], repo)
        clean_public = verify(repo, public)
        clean_heldout = verify(repo, heldout)
        if not clean_public or not clean_heldout:
            raise AssertionError('Invalid reference solution: ' + item['id'])
        mutated_file = mutate_solution(repo)
        mutant_public_pass = verify(repo, public)
        mutant_heldout_pass = verify(repo, heldout)
    return {
        'task': item['id'], 'category': item['category'],
        'mutated_file': mutated_file, 'reference_public_pass': clean_public,
        'reference_heldout_pass': clean_heldout,
        'mutant_public_pass': mutant_public_pass,
        'mutant_heldout_pass': mutant_heldout_pass,
        'public_killed': not mutant_public_pass,
        'heldout_killed': not mutant_heldout_pass,
    }


def run():
    with ThreadPoolExecutor(max_workers=6) as pool:
        rows = list(pool.map(audit_task, tasks()))
    n = len(rows)
    return {
        'method': 'first-return-replaced-with-None; one mutant per fixture',
        'limitations': [
            'Synthetic fixtures, not externally sourced real-world bugs',
            'One deterministic mutant per task; not a comprehensive mutation score',
            'A killed mutant does not establish model repair capability',
            'Trusted fixture execution only; no security sandbox',
        ],
        'tasks': n,
        'public_killed': sum(row['public_killed'] for row in rows),
        'heldout_killed': sum(row['heldout_killed'] for row in rows),
        'both_killed': sum(row['public_killed'] and row['heldout_killed'] for row in rows),
        'surviving_both': [row['task'] for row in rows if row['mutant_public_pass'] and row['mutant_heldout_pass']],
        'rows': rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='benchmark-hardening-results.json')
    args = parser.parse_args()
    report = run()
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: value for key, value in report.items() if key != 'rows'}, indent=2))


if __name__ == '__main__':
    main()
