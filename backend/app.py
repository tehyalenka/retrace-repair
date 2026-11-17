from backend.run_artifacts import save_run_artifacts
"""Local-only CodePilot-X dashboard API. Run from the CodePilot-X project root."""
import difflib
import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from codepilot.agent import run_agent
from codepilot.repository_analyzer import index_repository, rank_context_files, retrieve_context

ROOT = Path.cwd().resolve()
RUNS = {}
LOCK = threading.Lock()
MAX_RUNS = 30
app = FastAPI(title="CodePilot-X Dashboard API", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:4200", "http://127.0.0.1:4200"], allow_credentials=False, allow_methods=["GET", "POST"], allow_headers=["Content-Type"])

class RepositoryRequest(BaseModel):
    repository: str = "."

class RetrievalRequest(RepositoryRequest):
    task: str = Field(min_length=3, max_length=3000)
    max_files: int = Field(default=6, ge=1, le=30)
    strategy: str = "lexical"

class RunRequest(RetrievalRequest):
    attempts: int = Field(default=2, ge=1, le=5)
    generate_tests: bool = False
    repair_policy: str = "standard"


def safe_repo(value):
    # Never allow arbitrary filesystem traversal through the HTTP interface.
    candidate = (ROOT / value).resolve()
    if candidate != ROOT and ROOT not in candidate.parents:
        raise HTTPException(400, "Repository must be inside the CodePilot-X root")
    if not candidate.is_dir():
        raise HTTPException(404, "Repository directory not found")
    return candidate


def relative_files(repo):
    return [entry for entry in index_repository(repo) if not any(part.startswith(".") for part in Path(entry["path"]).parts)]


def report_files():
    patterns = (
        "benchmarks/**/retrieval_report*.json",
        "v*-live*.json",
        "benchmarks/**/v*-live*.json",
        "evaluation/reports/*.json",
    )

    matches = set()

    for pattern in patterns:
        for path in ROOT.glob(pattern):
            if path.is_file() and not path.is_symlink():
                matches.add(path)

    return sorted(matches)[:100]

@app.get("/api/health")
def health():
    return {"status": "ok", "root": str(ROOT), "provider": os.environ.get("CODEPILOT_PROVIDER", "groq"), "model": os.environ.get("CODEPILOT_MODEL", "openai/gpt-oss-120b"), "api_key_configured": bool(os.environ.get("GROQ_API_KEY") or os.environ.get("OPENAI_API_KEY"))}

@app.get("/api/repositories")
def repositories():
    excluded = {
        ".git", ".venv", "venv", "node_modules",
        "__pycache__", ".codepilot-runs"
    }

    discovered = set()

    for parent in ROOT.iterdir():
        if not parent.is_dir() or parent.name in excluded or parent.name.startswith("."):
            continue

        if parent.is_symlink():
            continue

        if any(parent.glob("*.py")) or any(parent.rglob("*.py")):
            discovered.add(parent.relative_to(ROOT).as_posix())

        for child in parent.iterdir():
            if (
                child.is_dir()
                and not child.is_symlink()
                and child.name not in excluded
                and not child.name.startswith(".")
                and any(child.glob("*.py"))
            ):
                discovered.add(child.relative_to(ROOT).as_posix())

    return {"repositories": ["."] + sorted(discovered)[:100]}


@app.post("/api/repository")
def repository(request: RepositoryRequest):
    repo = safe_repo(request.repository)
    entries = relative_files(repo)
    return {"repository": request.repository, "files": entries, "count": len(entries)}

@app.get("/api/file")
def file_content(repository: str = ".", path: str = ""):
    repo = safe_repo(repository)
    target = (repo / path).resolve()
    if target == repo or repo not in target.parents or not target.is_file() or target.suffix != ".py" or target.is_symlink():
        raise HTTPException(400, "Only repository Python files are readable")
    if target.stat().st_size > 200_000:
        raise HTTPException(413, "File too large")
    return {"path": path, "content": target.read_text(encoding="utf-8")}

@app.post("/api/retrieval")
def retrieval(request: RetrievalRequest):
    repo = safe_repo(request.repository)
    if request.strategy not in ("lexical", "dependency"):
        raise HTTPException(400, "Invalid retrieval strategy")
    entries = relative_files(repo)
    # Supports both the earlier and the updated ranker signatures.
    try:
        ranked = rank_context_files(entries, request.task, strategy=request.strategy, repo_path=repo)
    except TypeError as exc:
        if "repo_path" not in str(exc):
            raise
        ranked = rank_context_files(entries, request.task, strategy=request.strategy)
    context = retrieve_context(repo, request.task, max_files=request.max_files, strategy=request.strategy)
    return {"strategy": request.strategy, "ranking": ranked[:request.max_files], "context": context, "total_files": len(entries)}


def execute(run_id, request):
    try:
        result = run_agent(str(safe_repo(request.repository)), request.task, attempts=request.attempts, max_files=request.max_files, generate_tests=request.generate_tests, retrieval_strategy=request.strategy, repair_policy=request.repair_policy)
        with LOCK:
            RUNS[run_id].update(status="completed", result=result, finished_at=datetime.now(timezone.utc).isoformat())
            saved_run = dict(RUNS[run_id])
        try:
            save_run_artifacts(ROOT, saved_run)
        except (OSError, ValueError, TypeError) as artifact_error:
            with LOCK:
                RUNS[run_id]["artifact_error"] = (
                    f"{type(artifact_error).__name__}: {artifact_error}"
                )
    except Exception as exc:
        with LOCK:
            RUNS[run_id].update(status="error", error=f"{type(exc).__name__}: {str(exc)[:300]}", finished_at=datetime.now(timezone.utc).isoformat())

@app.post("/api/runs", status_code=202)
def create_run(request: RunRequest):
    safe_repo(request.repository)
    if request.repair_policy not in ("standard", "counterfactual", "counterfactual_replay"):
        raise HTTPException(400, "Invalid repair policy")
    if request.strategy not in ("lexical", "dependency"):
        raise HTTPException(400, "Invalid retrieval strategy")
    with LOCK:
        if any(r["status"] == "running" for r in RUNS.values()):
            raise HTTPException(409, "Another agent run is already in progress")
        if len(RUNS) >= MAX_RUNS:
            oldest = next(iter(RUNS))
            RUNS.pop(oldest)
        run_id = uuid.uuid4().hex[:12]
        RUNS[run_id] = {"id": run_id, "status": "running", "task": request.task, "repository": request.repository, "started_at": datetime.now(timezone.utc).isoformat(), "result": None,
                        "execution_provenance": {
                            "source": "codepilot_agent",
                            "execution_mode": "autonomous",
                            "recorded_at_creation": True
                        }}
    threading.Thread(target=execute, args=(run_id, request), daemon=True).start()
    return {"id": run_id, "status": "running"}


def load_saved_runs():
    """Load completed runs saved on disk."""
    saved = {}

    directory = ROOT / ".codepilot-runs"

    if not directory.is_dir():
        return saved

    for metadata in directory.glob("*/run.json"):
        try:
            if metadata.is_symlink():
                continue

            record = json.loads(
                metadata.read_text(encoding="utf-8")
            )

            run_id = record.get("id")

            if (
                run_id != metadata.parent.name
                or not isinstance(run_id, str)
                or len(run_id) != 12
                or any(c not in "0123456789abcdef" for c in run_id)
                or record.get("status") != "completed"
                or not isinstance(record.get("result"), dict)
            ):
                continue

            saved[run_id] = record

        except (OSError, ValueError, TypeError):
            continue

    return saved


@app.get("/api/runs")
def list_runs():
    combined = load_saved_runs()

    with LOCK:
        combined.update(RUNS)

    ordered = sorted(
        combined.values(),
        key=lambda run: run.get("started_at") or "",
        reverse=True,
    )

    return {
        "runs": [
            {
                **{k: v for k, v in run.items() if k != "result"},
                "success": (run.get("result") or {}).get("success"),
            }
            for run in ordered[:MAX_RUNS]
        ]
    }

@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    with LOCK:
        current = RUNS.get(run_id)

    if current is not None:
        return current

    saved = load_saved_runs().get(run_id)

    if saved is None:
        raise HTTPException(404, "Run not found")

    return saved

@app.get("/api/benchmarks")
def benchmarks():
    records = []
    for path in report_files():
        try:
            if path.stat().st_size > 5_000_000:
                continue
            content = json.loads(path.read_text(encoding="utf-8"))
            records.append({"name": path.name, "path": str(path.relative_to(ROOT)), "data": content})
        except (ValueError, OSError):
            continue
    return {"reports": records}

@app.get("/api/diff/{run_id}")
def run_diff(run_id: str):
    with LOCK:
        run = RUNS.get(run_id)

    if run is None:
        run = load_saved_runs().get(run_id)

    if not run or not run.get("result"):
        raise HTTPException(404, "Run result not found")
    repo = safe_repo(run["repository"]).resolve()
    diffs = {}

    snapshot_dir = ROOT / ".codepilot-runs" / run_id / "original"

    for name, updated in run["result"].get("files", {}).items():
        relative = Path(name)

        if (
            relative.is_absolute()
            or ".." in relative.parts
            or relative.suffix != ".py"
        ):
            continue

        snapshot = snapshot_dir / relative
        target = (repo / relative).resolve()

        if repo not in target.parents:
            continue

        if snapshot.is_file() and not snapshot.is_symlink():
            original = snapshot.read_text(encoding="utf-8")
        elif snapshot_dir.is_dir():
            # Do not use mutable repository contents if snapshots exist.
            continue
        else:
            # Compatibility with runs saved before snapshot support.
            original = (
                target.read_text(encoding="utf-8")
                if target.is_file() and not target.is_symlink()
                else ""
            )

        diffs[name] = "".join(
            difflib.unified_diff(
                original.splitlines(True),
                (updated or "").splitlines(True),
                fromfile="original/" + name,
                tofile="agent/" + name,
            )
        )

    return {"diffs": diffs}


@app.get("/api/artifacts/{run_id}")
def get_artifacts(run_id: str):
    import re

    if not re.fullmatch(r"[a-f0-9]{12}", run_id):
        raise HTTPException(400, "Invalid run ID")

    directory = ROOT / ".codepilot-runs" / run_id
    metadata = directory / "run.json"

    if not metadata.is_file():
        raise HTTPException(404, "Saved run not found")

    return json.loads(metadata.read_text(encoding="utf-8"))


@app.get("/api/artifacts/{run_id}/download")
def download_artifacts(run_id: str):
    import io
    import re
    import zipfile

    from fastapi.responses import StreamingResponse

    if not re.fullmatch(r"[a-f0-9]{12}", run_id):
        raise HTTPException(400, "Invalid run ID")

    directory = ROOT / ".codepilot-runs" / run_id
    generated = directory / "generated"

    if not generated.is_dir():
        raise HTTPException(404, "Generated files not found")

    buffer = io.BytesIO()

    with zipfile.ZipFile(
        buffer, "w", zipfile.ZIP_DEFLATED
    ) as archive:
        for path in sorted(generated.rglob("*.py")):
            if path.is_symlink():
                continue

            archive.write(
                path,
                arcname=str(path.relative_to(generated)),
            )

    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition":
                f'attachment; filename="codepilot-{run_id}.zip"'
        },
    )


@app.post("/api/artifacts/{run_id}/verify")
def verify_artifacts(run_id: str):
    import re

    from backend.independent_verification import verify_generated_files

    if not re.fullmatch(r"[a-f0-9]{12}", run_id):
        raise HTTPException(400, "Invalid run ID")

    directory = ROOT / ".codepilot-runs" / run_id
    metadata = directory / "run.json"
    generated = directory / "generated"

    if not metadata.is_file():
        raise HTTPException(404, "Saved run not found")

    run = json.loads(metadata.read_text(encoding="utf-8"))
    repo = safe_repo(run["repository"])

    if not generated.is_dir():
        raise HTTPException(404, "Generated files not found")

    try:
        verification = verify_generated_files(repo, generated)
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    (directory / "verification.json").write_text(
        json.dumps(verification, indent=2),
        encoding="utf-8",
    )

    return verification
