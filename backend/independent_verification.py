"""Local independent verification of saved agent-generated code."""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath


def verify_generated_files(repo, generated, timeout=30):
    repo = Path(repo).resolve()
    generated = Path(generated).resolve()

    if not generated.is_dir():
        raise ValueError("Generated artifacts directory not found")

    if not (repo / "independent_tests").is_dir():
        raise ValueError(
            "Repository has no independent_tests directory"
        )

    with tempfile.TemporaryDirectory(prefix="codepilot-verify-") as temp:
        workspace = Path(temp) / "repository"

        shutil.copytree(
            repo,
            workspace,
            ignore=shutil.ignore_patterns(
                ".git", ".venv", "__pycache__", ".pytest_cache"
            ),
        )

        applied = []

        for source in generated.rglob("*.py"):
            if source.is_symlink():
                raise ValueError("Symlinked generated file rejected")

            relative = source.relative_to(generated)
            safe_path = PurePosixPath(relative.as_posix())

            if ".." in safe_path.parts:
                raise ValueError("Unsafe generated file path")

            if any(
                part in ("tests", "independent_tests", "__pycache__")
                for part in safe_path.parts
            ):
                raise ValueError(
                    "Generated artifacts cannot overwrite test files"
                )

            destination = workspace.joinpath(*safe_path.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source.read_bytes())
            applied.append(relative.as_posix())

        command = [
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            "independent_tests",
            "-p",
            "test_*.py",
            "-v",
        ]

        try:
            completed = subprocess.run(
                command,
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=timeout,
                env={
                    "PATH": "/usr/bin:/bin",
                    "PYTHONPATH": str(workspace),
                    "PYTHONDONTWRITEBYTECODE": "1",
                },
            )

            return {
                "passed": completed.returncode == 0,
                "returncode": completed.returncode,
                "output": (
                    completed.stdout + "\n" + completed.stderr
                )[-20000:],
                "applied_files": applied,
                "timed_out": False,
            }

        except subprocess.TimeoutExpired:
            return {
                "passed": False,
                "returncode": None,
                "output": "Independent verification timed out",
                "applied_files": applied,
                "timed_out": True,
            }
