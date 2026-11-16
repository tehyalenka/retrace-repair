"""Safe, lightweight Python repository inventory and lexical retrieval."""
import ast
from pathlib import Path
import re

EXCLUDED_DIRS = {".venv", "venv", ".git", "__pycache__", "node_modules", ".tox", "dist", "build"}


def discover_python_files(repo_path):
    repo = Path(repo_path).expanduser().resolve()
    if not repo.exists():
        raise FileNotFoundError("Repository does not exist: {}".format(repo))
    if not repo.is_dir():
        raise NotADirectoryError("Not a directory: {}".format(repo))
    result = []
    for path in repo.rglob("*.py"):
        rel = path.relative_to(repo)
        if any(part in EXCLUDED_DIRS for part in rel.parts):
            continue
        if path.is_symlink() or not path.is_file():
            continue
        result.append(rel.as_posix())
    return sorted(result)


def inspect_file(repo_path, relative_path):
    path = Path(repo_path).resolve() / relative_path
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=relative_path)
        functions, classes, imports = [], [], []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append({"name": node.name, "line": node.lineno})
            elif isinstance(node, ast.ClassDef):
                classes.append({"name": node.name, "line": node.lineno})
            elif isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")
        return {"path": relative_path, "functions": functions, "classes": classes,
                "imports": sorted(set(imports)), "syntax_error": None, "lines": len(source.splitlines())}
    except (SyntaxError, UnicodeError, OSError) as exc:
        return {"path": relative_path, "functions": [], "classes": [], "imports": [],
                "syntax_error": str(exc), "lines": 0}


def index_repository(repo_path):
    return [inspect_file(repo_path, path) for path in discover_python_files(repo_path)]


def _module_names(relative_path):
    """Possible import names for a Python file, including package __init__."""
    parts = list(Path(relative_path).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return {".".join(parts)} if parts else set()


def dependency_graph(entries, repo_path=None):
    """Return deterministic repository-local dependency relationships.

    Supports:
    - Direct imports
    - Unique class references in type annotations
    - Unique class constructor calls

    Ambiguous class names are ignored.
    """
    modules = {}

    for item in entries:
        for name in _module_names(item["path"]):
            modules[name] = item["path"]

    graph = {item["path"]: set() for item in entries}

    # Preserve existing import-based relationships.
    for item in entries:
        for imported in item["imports"]:
            parts = imported.split(".")

            for length in range(len(parts), 0, -1):
                target = modules.get(".".join(parts[:length]))

                if target and target != item["path"]:
                    graph[item["path"]].add(target)
                    break

    # Build a map of uniquely defined repository-local classes.
    class_owners = {}

    for item in entries:
        for cls in item["classes"]:
            class_owners.setdefault(cls["name"], set()).add(
                item["path"]
            )

    unique_classes = {
        name: next(iter(owners))
        for name, owners in class_owners.items()
        if len(owners) == 1
    }

    # AST symbol analysis requires access to the source files.
    if repo_path is not None:
        root = Path(repo_path).resolve()

        for item in entries:
            source_path = root / item["path"]

            try:
                tree = ast.parse(
                    source_path.read_text(encoding="utf-8")
                )
            except (OSError, UnicodeError, SyntaxError):
                continue

            for node in ast.walk(tree):
                referenced = None

                # Typed arguments and return annotations.
                if isinstance(node, ast.arg):
                    annotation = node.annotation

                    if isinstance(annotation, ast.Name):
                        referenced = annotation.id

                # Direct constructor calls, e.g. Inventory().
                elif isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        referenced = node.func.id

                if referenced in unique_classes:
                    target = unique_classes[referenced]

                    if target != item["path"]:
                        graph[item["path"]].add(target)

    return {
        path: sorted(neighbors)
        for path, neighbors in sorted(graph.items())
    }



def rank_context_files(entries, task, strategy="lexical", repo_path=None):
    """Rank files without reading test outcomes or independent verification.

    Dependency mode expands strong lexical matches by one import edge in
    either direction. It never gives a zero-relevance file a higher score
    than a direct lexical match with score >= 3.
    """
    if strategy not in ("lexical", "dependency"):
        raise ValueError("Unknown retrieval strategy: {}".format(strategy))
    tokens = set(re.findall(r"[a-zA-Z_][a-zA-Z_0-9]*", task.lower()))
    scores = {}
    for item in entries:
        terms = re.findall(r"[a-zA-Z_][a-zA-Z_0-9]*", item["path"].lower())
        terms += [f["name"].lower() for f in item["functions"]]
        terms += [c["name"].lower() for c in item["classes"]]
        score = sum(3 for term in terms if term in tokens)
        if item["path"].startswith("tests/") or "/test_" in item["path"]:
            score += 1
        scores[item["path"]] = score
    if strategy == "dependency":
        graph = dependency_graph(entries, repo_path=repo_path)
        reverse = {path: set() for path in graph}
        for source, targets in graph.items():
            for target in targets:
                reverse[target].add(source)
        bonus = {path: 0 for path in scores}
        for path, score in scores.items():
            if score >= 3:
                for neighbor in set(graph[path]) | reverse[path]:
                    bonus[neighbor] = max(bonus[neighbor], 2)
        scores = {path: score + bonus[path] for path, score in scores.items()}
    return sorted(scores, key=lambda path: (-scores[path], path))


def retrieve_context(repo_path, task, max_files=6, max_chars=22000, strategy="lexical"):
    entries = index_repository(repo_path)

    # Exclude tests from implementation context unless requested.
    task_lower = task.lower()
    include_tests = any(
        phrase in task_lower
        for phrase in (
            "write tests",
            "add tests",
            "update tests",
            "fix tests",
            "modify tests",
        )
    )

    if not include_tests:
        entries = [
            item for item in entries
            if not (
                item["path"].startswith("tests/")
                or item["path"].split("/")[-1].startswith("test_")
                or item["path"].split("/")[-1].endswith("_test.py")
            )
        ]

    ranked = rank_context_files(entries, task, strategy=strategy, repo_path=repo_path)
    chunks = []
    remaining = max_chars
    for relative in ranked[:max_files]:
        content = (Path(repo_path) / relative).read_text(encoding="utf-8", errors="replace")
        section = "### {}\n{}".format(relative, content)
        if remaining <= 0:
            break
        chunks.append(section[:remaining])
        remaining -= len(chunks[-1])
    return "\n\n".join(chunks)


def repository_map(repo_path, max_chars=14000):
    """Compact, deterministic inventory of modules, symbols, and imports."""
    lines = []
    for item in index_repository(repo_path):
        symbols = [f["name"] for f in item["functions"]] + [c["name"] for c in item["classes"]]
        line = "{} | imports: {} | symbols: {}".format(item["path"], ", ".join(item["imports"][:12]), ", ".join(symbols[:20]))
        if item["syntax_error"]:
            line += " | parse-error: " + item["syntax_error"][:100]
        lines.append(line)
    result = "\n".join(lines)
    return result[:max_chars] + ("\n[map truncated]" if len(result) > max_chars else "")
