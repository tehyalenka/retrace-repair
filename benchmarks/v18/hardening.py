"""Offline benchmark hardening with multi-operator mutation analysis.

Trusted fixtures only; NOT a security sandbox.
Evaluates independent public and heldout verifier strength against semantic faults:
1. ReplaceFirstReturn (first return value -> None)
2. FlipFirstComparison (comparison operator inversion == -> !=, < -> >=, in -> not in)
3. OffByOne (integer constant off-by-one perturbation +1)
4. DeleteFirstStatement (first non-docstring statement deletion)
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


class FlipFirstComparison(ast.NodeTransformer):
    """Invert the first comparison operator (e.g., == to !=, < to >=)."""
    def __init__(self):
        self.changed = False

    def visit_Compare(self, node):
        if not self.changed and node.ops:
            op = node.ops[0]
            mapping = {
                ast.Eq: ast.NotEq,
                ast.NotEq: ast.Eq,
                ast.Lt: ast.GtE,
                ast.LtE: ast.Gt,
                ast.Gt: ast.LtE,
                ast.GtE: ast.Lt,
                ast.In: ast.NotIn,
                ast.NotIn: ast.In,
                ast.Is: ast.IsNot,
                ast.IsNot: ast.Is,
            }
            for src, dst in mapping.items():
                if isinstance(op, src):
                    self.changed = True
                    node.ops[0] = dst()
                    return node
        return node


class OffByOne(ast.NodeTransformer):
    """Perturb the first integer constant by +1."""
    def __init__(self):
        self.changed = False

    def visit_Constant(self, node):
        if not self.changed and isinstance(node.value, int) and type(node.value) is int:
            self.changed = True
            return ast.copy_location(ast.Constant(value=node.value + 1), node)
        return node


class DeleteFirstStatement(ast.NodeTransformer):
    """Delete the first executable statement of the first function with multiple statements."""
    def __init__(self):
        self.changed = False

    def visit_FunctionDef(self, node):
        if not self.changed and len(node.body) > 1:
            idx = 0
            if (isinstance(node.body[0], ast.Expr) and
                    isinstance(node.body[0].value, ast.Constant) and
                    isinstance(node.body[0].value.value, str)):
                idx = 1
            if len(node.body) > idx:
                self.changed = True
                node.body.pop(idx)
                return node
        return self.generic_visit(node)


MUTATION_OPERATORS = {
    "return_none": ReplaceFirstReturn,
    "flip_comparison": FlipFirstComparison,
    "off_by_one": OffByOne,
    "delete_statement": DeleteFirstStatement,
}


def mutate_solution_with_operator(repo, operator_cls):
    """Apply one syntactically valid semantic mutation using the specified operator."""
    for path in sorted(repo.rglob("*.py")):
        if any(part in ("tests", "__pycache__") for part in path.parts):
            continue
        original = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(original, filename=str(path))
        except SyntaxError:
            continue
        transformer = operator_cls()
        tree = transformer.visit(tree)
        if transformer.changed:
            ast.fix_missing_locations(tree)
            path.write_text(ast.unparse(tree) + "\n", encoding="utf-8")
            return str(path.relative_to(repo))
    return None


def mutate_solution(repo):
    """Default backward-compatible mutator: replace first return with None."""
    res = mutate_solution_with_operator(repo, ReplaceFirstReturn)
    if res is not None:
        return res
    raise ValueError("No return statement available to mutate: " + str(repo))


def audit_task_mutant(item, op_name, op_cls):
    """Evaluate whether independent public/heldout tests kill a specific mutant."""
    public = (ROOT / item["public_verifier"]).read_text(encoding="utf-8")
    heldout = (ROOT / item["heldout_verifier"]).read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="retrace-hardening-") as temp:
        repo = Path(temp) / "solution"
        shutil.copytree(ROOT / item["solution"], repo)
        clean_public = verify(repo, public)
        clean_heldout = verify(repo, heldout)
        if not clean_public or not clean_heldout:
            raise AssertionError("Invalid reference solution: " + item["id"])
        mutated_file = mutate_solution_with_operator(repo, op_cls)
        if mutated_file is None:
            return None
        mutant_public_pass = verify(repo, public)
        mutant_heldout_pass = verify(repo, heldout)
    return {
        "task": item["id"],
        "category": item["category"],
        "operator": op_name,
        "mutated_file": mutated_file,
        "reference_public_pass": clean_public,
        "reference_heldout_pass": clean_heldout,
        "mutant_public_pass": mutant_public_pass,
        "mutant_heldout_pass": mutant_heldout_pass,
        "public_killed": not mutant_public_pass,
        "heldout_killed": not mutant_heldout_pass,
        "killed": (not mutant_public_pass) or (not mutant_heldout_pass),
    }


def audit_task(item):
    """Evaluate default return_none mutation for backward compatibility."""
    res = audit_task_mutant(item, "return_none", ReplaceFirstReturn)
    if res is None:
        raise ValueError("No return statement available to mutate: " + item["id"])
    return res


def run(operator=None):
    if operator is None or operator == "return_none":
        with ThreadPoolExecutor(max_workers=6) as pool:
            rows = list(pool.map(audit_task, tasks()))
        n = len(rows)
        return {
            "method": "first-return-replaced-with-None; one mutant per fixture",
            "limitations": [
                "Synthetic fixtures, not externally sourced real-world bugs",
                "One deterministic mutant per task; not a comprehensive mutation score",
                "A killed mutant does not establish model repair capability",
                "Trusted fixture execution only; no security sandbox",
            ],
            "tasks": n,
            "public_killed": sum(row["public_killed"] for row in rows),
            "heldout_killed": sum(row["heldout_killed"] for row in rows),
            "both_killed": sum(row["public_killed"] and row["heldout_killed"] for row in rows),
            "surviving_both": [row["task"] for row in rows if row["mutant_public_pass"] and row["mutant_heldout_pass"]],
            "rows": rows,
        }

    all_tasks = tasks()
    jobs = []
    if operator in MUTATION_OPERATORS:
        selected_ops = [(operator, MUTATION_OPERATORS[operator])]
    else:
        selected_ops = list(MUTATION_OPERATORS.items())

    for item in all_tasks:
        for op_name, op_cls in selected_ops:
            jobs.append((item, op_name, op_cls))

    def _worker(job):
        item, op_name, op_cls = job
        return audit_task_mutant(item, op_name, op_cls)

    with ThreadPoolExecutor(max_workers=6) as pool:
        raw_rows = list(pool.map(_worker, jobs))

    rows = [r for r in raw_rows if r is not None]
    total_mutants = len(rows)
    total_killed = sum(1 for r in rows if r["killed"])

    operator_breakdown = {}
    for op_name, _ in selected_ops:
        op_rows = [r for r in rows if r["operator"] == op_name]
        op_count = len(op_rows)
        op_killed = sum(1 for r in op_rows if r["killed"])
        operator_breakdown[op_name] = {
            "mutants": op_count,
            "killed": op_killed,
            "kill_rate": round(op_killed / op_count, 4) if op_count else 1.0,
        }

    return {
        "method": f"multi-operator-mutations ({', '.join(k for k, _ in selected_ops)})",
        "limitations": [
            "Synthetic fixtures, not externally sourced real-world bugs",
            "Multi-operator AST mutations evaluate test sensitivity, not complete coverage",
            "A killed mutant validates test sensitivity, not autonomous repair capability",
            "Trusted fixture execution only; no security sandbox",
        ],
        "tasks": len(all_tasks),
        "total_mutants": total_mutants,
        "total_killed": total_killed,
        "mutation_score_percent": round(total_killed / total_mutants * 100, 2) if total_mutants else 100.0,
        "public_killed": sum(1 for r in rows if r["public_killed"]),
        "heldout_killed": sum(1 for r in rows if r["heldout_killed"]),
        "both_killed": sum(1 for r in rows if r["public_killed"] and r["heldout_killed"]),
        "operator_breakdown": operator_breakdown,
        "surviving_both": [f"{r['task']}:{r['operator']}" for r in rows if not r["killed"]],
        "rows": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operator", default="all", choices=["all", "return_none", "flip_comparison", "off_by_one", "delete_statement"])
    parser.add_argument("--output", default="benchmark-hardening-results.json")
    args = parser.parse_args()
    report = run(operator=args.operator)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    summary = {k: v for k, v in report.items() if k != "rows"}
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
