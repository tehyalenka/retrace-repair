"""Persist generated CodePilot-X run artifacts locally."""

import json
import re
from pathlib import Path, PurePosixPath


def save_run_artifacts(root, run):
    run_id = run["id"]

    if not re.fullmatch(r"[a-f0-9]{12}", run_id):
        raise ValueError("Invalid run ID")

    root = Path(root).resolve()
    repo = (root / run["repository"]).resolve()

    if repo != root and root not in repo.parents:
        raise ValueError("Repository outside project root")

    if not repo.is_dir():
        raise ValueError("Repository not found")

    destination = root / ".codepilot-runs" / run_id
    generated = destination / "generated"
    original = destination / "original"

    result = run.get("result") or {}
    files = result.get("files") or {}

    # Validate paths before writing artifacts.
    validated = []

    for filename, content in files.items():
        relative = PurePosixPath(filename)

        if (
            relative.is_absolute()
            or ".." in relative.parts
            or not relative.parts
            or relative.suffix != ".py"
            or "\\" in filename
        ):
            raise ValueError("Unsafe generated file path")

        source_file = repo.joinpath(*relative.parts)
        resolved_source = source_file.resolve()

        if (
            resolved_source == repo
            or repo not in resolved_source.parents
            or source_file.is_symlink()
        ):
            raise ValueError("Unsafe original file path")

        if source_file.exists() and not source_file.is_file():
            raise ValueError("Original path is not a file")

        validated.append((relative, content, source_file))

    generated.mkdir(parents=True, exist_ok=True)
    original.mkdir(parents=True, exist_ok=True)

    for relative, content, source_file in validated:
        generated_target = generated.joinpath(*relative.parts)
        original_target = original.joinpath(*relative.parts)

        generated_target.parent.mkdir(parents=True, exist_ok=True)
        original_target.parent.mkdir(parents=True, exist_ok=True)

        if generated_target.is_symlink() or original_target.is_symlink():
            raise ValueError("Refusing to overwrite a symlink")

        original_content = (
            source_file.read_text(encoding="utf-8")
            if source_file.is_file()
            else ""
        )

        original_target.write_text(
            original_content,
            encoding="utf-8",
        )

        generated_target.write_text(
            content or "",
            encoding="utf-8",
        )

    metadata = {
        "id": run_id,
        "repository": run["repository"],
        "task": run["task"],
        "status": run["status"],
        "started_at": run["started_at"],
        "execution_provenance": run.get("execution_provenance"),
        "provider": run.get("provider"),
        "model": run.get("model"),
        "finished_at": run.get("finished_at"),
        "success": result.get("success"),
        "generated_files": list(files),
        "result": result,
    }

    (destination / "run.json").write_text(
        json.dumps(metadata, indent=2, default=str),
        encoding="utf-8",
    )

    return destination
