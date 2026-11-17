
"""LLM-assisted coding agent. Never edits the user's original repository."""
import json
from contextvars import ContextVar
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import requests
import time
import random
import re
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
import tempfile

from .repository_analyzer import retrieve_context, discover_python_files, repository_map

SYSTEM = """You are a careful Python software engineer working in a disposable repository copy.
Return ONLY valid JSON of this shape:
{"reasoning_summary":"brief explanation", "edits":[{"path":"relative/path.py", "operation":"modify|create|delete", "content":"COMPLETE file contents for create/modify"}]}
For existing Python files, use operation=modify. For a new Python file use operation=create.
Use operation=delete only when essential; omit content for delete. Never issue shell commands.
Coordinate changes across modules, update imports and callers, and preserve unrelated behavior.
You may modify or delete existing Python files and create new Python files under existing directories.
Do not edit test files unless the task specifically requires tests. Do not modify secrets or dependencies.
Use the repository map to understand relationships; context may omit files, so avoid assumptions.
Do not use markdown fences.
"""


def provider_config():
    """Select Groq, Gemini, or OpenAI using environment variables."""

    provider = os.environ.get(
        "CODEPILOT_PROVIDER", "groq"
    ).strip().lower()

    if provider == "groq":
        key_name = "GROQ_API_KEY"
        default_model = "openai/gpt-oss-120b"
        base_url = "https://api.groq.com/openai/v1"

    elif provider == "gemini":
        key_name = "GEMINI_API_KEY"
        default_model = "gemini-2.5-flash"
        base_url = (
            "https://generativelanguage.googleapis.com"
            "/v1beta/openai"
        )

    elif provider == "openai":
        key_name = "OPENAI_API_KEY"
        default_model = "gpt-4o-mini"
        base_url = "https://api.openai.com/v1"

    else:
        raise ValueError(
            "Unsupported CODEPILOT_PROVIDER: {} "
            "(use groq, gemini, or openai)".format(provider)
        )

    key = os.environ.get(key_name)

    if not key:
        raise RuntimeError(
            "{} is not set. Export it before running the agent."
            .format(key_name)
        )

    model = os.environ.get(
        "CODEPILOT_MODEL", default_model
    )

    return key, model, base_url


_ACTIVE_MODEL_ACCOUNTING = ContextVar(
    "retrace_model_accounting", default=None
)


class ModelRequestAccounting:
    """Scoped model request accounting."""

    def __init__(self):
        self.logical_calls = 0
        self.http_requests = 0
        self.http_failures = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.usage_reports = 0

    def snapshot(self):
        return {
            "logical_calls": self.logical_calls,
            "http_requests": self.http_requests,
            "http_failures": self.http_failures,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "usage_reports": self.usage_reports,
        }

    def __enter__(self):
        self._token = _ACTIVE_MODEL_ACCOUNTING.set(self)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        _ACTIVE_MODEL_ACCOUNTING.reset(self._token)


class LLMAPIError(RuntimeError):
    """Non-secret, user-readable provider error."""


def _retry_delay(response, retry_number):
    """Calculate provider-requested delay; never silently shorten it."""
    header = response.headers.get("Retry-After", "")
    try:
        wait = float(header)
    except (ValueError, TypeError):
        try:
            wait = (parsedate_to_datetime(header) - datetime.now(timezone.utc)).total_seconds()
        except (TypeError, ValueError, OverflowError):
            wait = None
    if wait is None:
        try:
            detail = response.json().get("error", {}).get("message", "")
        except (ValueError, AttributeError):
            detail = ""
        match = re.search(r"try again in\s+([0-9.]+)s", detail, re.IGNORECASE)
        wait = float(match.group(1)) if match else min(2 ** retry_number, 16)
    return max(wait, 0.0) + 0.25


def ask_model(messages, model=None, base_url=None, json_mode=None, temperature=None):
    key, default_model, default_base_url = provider_config()
    model = model or default_model
    base_url = (base_url or default_base_url).rstrip("/")

    if temperature is None:
        temperature = os.environ.get("CODEPILOT_TEMPERATURE", "0")

    try:
        temperature = float(temperature)
    except (TypeError, ValueError) as exc:
        raise ValueError("Temperature must be a number") from exc

    if not 0 <= temperature <= 2:
        raise ValueError("Temperature must be between 0 and 2")

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    # Explicit override enables controlled A/B experiments without mutating the environment.
    if json_mode is None:
        json_mode = os.environ.get("CODEPILOT_JSON_MODE", "0") == "1"
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    max_retries = int(os.environ.get("CODEPILOT_MAX_RETRIES", "3"))
    if not 0 <= max_retries <= 10:
        raise ValueError("CODEPILOT_MAX_RETRIES must be between 0 and 10")
    max_retry_wait = 60.0  # Longer waits are deferred to benchmark --resume.
    accounting = _ACTIVE_MODEL_ACCOUNTING.get()
    if accounting is not None:
        accounting.logical_calls += 1

    for retry in range(max_retries + 1):
        try:
            if accounting is not None:
                accounting.http_requests += 1
            response = requests.post(
                base_url + "/chat/completions",
                headers={"Authorization": "Bearer " + key,
                         "Content-Type": "application/json"},
                json=payload, timeout=90)
        except requests.RequestException as exc:
            if accounting is not None:
                accounting.http_failures += 1
            if retry < max_retries:
                time.sleep(min(2 ** retry, 8))
                continue
            raise LLMAPIError("LLM connection failed after retries: {}".format(type(exc).__name__)) from exc
        if accounting is not None and response.status_code != 200:
            accounting.http_failures += 1

        if response.status_code in (429, 500, 502, 503, 504):
            delay = _retry_delay(response, retry)
            if response.status_code == 429 and delay > max_retry_wait:
                # Do not retry earlier than the provider requested. Preserve the
                # experiment's checkpoint and let the caller resume later.
                raise LLMAPIError(
                    "LLM API HTTP 429; provider requested a wait longer than "
                    "60 seconds; resume later")
            if retry < max_retries:
                time.sleep(min(delay, max_retry_wait))
                continue
            raise LLMAPIError("LLM API HTTP {} after {} retries; retry later".format(response.status_code, max_retries))
        if response.status_code != 200:
            # Never echo provider response bodies: they can contain sensitive data.
            raise LLMAPIError("LLM API HTTP {} (provider rejected request; check model and response format compatibility)".format(response.status_code))
        try:
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise ValueError("Empty model content")
            if accounting is not None:
                usage = result.get("usage")
                if isinstance(usage, dict):
                    prompt = usage.get("prompt_tokens")
                    completion = usage.get("completion_tokens")
                    if (
                        type(prompt) is int and prompt >= 0
                        and type(completion) is int and completion >= 0
                    ):
                        accounting.prompt_tokens += prompt
                        accounting.completion_tokens += completion
                        accounting.usage_reports += 1

            return content
        except (ValueError, TypeError, KeyError, IndexError) as exc:
            raise LLMAPIError("LLM returned an invalid completion envelope") from exc
    raise AssertionError("unreachable")


def _recover_quoted_edit_boundary(raw):
    """Recover exactly one extra quote between edit objects.

    Require the JSON decoder to fail at the candidate boundary, then demand
    that removing that one character yields a valid edits-shaped document.
    Do not attempt general JSON repair or alter any edit contents.
    """
    try:
        json.loads(raw)
        return None
    except json.JSONDecodeError as exc:
        error_pos = exc.pos

    marker = '},"{"path"'
    candidates = []
    start = 0
    while True:
        index = raw.find(marker, start)
        if index < 0:
            break
        candidates.append(index)
        start = index + 1
    if len(candidates) != 1:
        return None

    index = candidates[0]
    # The decoder reports the opening brace immediately after the stray
    # quotation mark in the observed malformed edit-object separator.
    if not index + 3 <= error_pos <= index + len(marker) + 2:
        return None
    corrected = raw[:index + 2] + raw[index + 3:]
    try:
        data = json.loads(corrected)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or not isinstance(data.get('edits'), list):
        return None
    if len(data['edits']) < 2 or not all(isinstance(e, dict) for e in data['edits']):
        return None
    return corrected


def parse_edits(answer):
    raw = answer.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        corrected = _recover_quoted_edit_boundary(raw)
        if corrected is None:
            raise
        data = json.loads(corrected)
    if not isinstance(data, dict) or not isinstance(data.get("edits"), list):
        raise ValueError("Model did not return an edits array")
    # JSON syntax alone is insufficient: a valid edits batch needs objects.
    # Validate the response shape here so formatting retries can repair it
    # without consuming an implementation/test attempt.
    for index, edit in enumerate(data["edits"]):
        if not isinstance(edit, dict):
            raise ValueError("Edit {} must be an object".format(index))
        if not isinstance(edit.get("path"), str) or not edit["path"]:
            raise ValueError("Edit {} requires a nonempty path".format(index))
        operation = edit.get("operation", "modify")
        if operation not in ("create", "modify", "delete"):
            raise ValueError("Edit {} has an invalid operation".format(index))
        if operation != "delete" and not isinstance(edit.get("content"), str):
            raise ValueError("Edit {} requires complete source content".format(index))
    return data


def parse_edits_with_format_retry(messages, answer, format_retries=2, diagnostics=None, json_mode=None):
    """Ask for a clean re-serialization when the model emits invalid edit JSON.

    Keep the original response as context, but do not execute or partially apply it.
    Formatting retries are separate from the implementation attempt budget.
    """
    current = answer
    if diagnostics is not None:
        diagnostics["format_repair_succeeded"] = False
    if diagnostics is not None:
        diagnostics["format_retries_used"] = 0
    for retry in range(format_retries + 1):
        try:
            parsed = parse_edits(current)
            parsed["_validated_raw_answer"] = current
            if diagnostics is not None:
                diagnostics["format_repair_succeeded"] = retry > 0
            return parsed
        except (json.JSONDecodeError, ValueError) as exc:
            if retry == format_retries:
                raise ValueError("Invalid edit JSON after {} formatting retries: {}".format(format_retries, exc)) from exc
            correction = list(messages) + [
                {"role": "assistant", "content": current},
                {"role": "user", "content": (
                    "Your previous edit response was not valid edit-batch JSON ({}). "
                    "Return the SAME complete edit batch as ONE strictly valid JSON object. "
                    "Escape newlines and quotation marks inside content strings correctly. "
                    "Do not use markdown, comments, or unescaped control characters. "
                    "Do not omit any file or replace complete source with snippets."
                ).format(str(exc)[:300])},
            ]
            if diagnostics is not None:
                diagnostics["format_retries_used"] += 1
            current = ask_model(correction, json_mode=json_mode)
    raise AssertionError("unreachable")


def apply_edits(workspace, edits, allowed):
    """Validate the entire operation batch, then apply it with rollback on write errors.

    Existing-file modifications are restricted to the indexed allowlist. New files
    must be Python sources under existing, non-symlink directories. This is not
    a security sandbox; do not run untrusted repositories.
    """
    workspace = Path(workspace).resolve()
    if not isinstance(edits, list) or not 1 <= len(edits) <= 20:
        raise ValueError("Expected 1-20 file operations")
    pending, seen = [], set()
    for edit in edits:
        if not isinstance(edit, dict):
            raise ValueError("Edit must be an object")
        relative = edit.get("path")
        operation = edit.get("operation", "modify")
        if not isinstance(relative, str) or not relative or "\\" in relative:
            raise ValueError("Invalid relative path")
        parts = PurePosixPath(relative).parts
        if (PurePosixPath(relative).is_absolute() or not parts or
                any(part in (".", "..") for part in parts) or
                relative != PurePosixPath(relative).as_posix() or
                not relative.endswith(".py") or relative in seen):
            raise ValueError("Unsafe or duplicate file path: {}".format(relative))
        if any(part in (".git", ".venv", "__pycache__", "node_modules") for part in parts):
            raise ValueError("Excluded path: {}".format(relative))
        target = workspace.joinpath(*parts)
        if any(p.is_symlink() for p in [target, *target.parents] if p != workspace and workspace in p.parents):
            raise ValueError("Symlink path is forbidden")
        if workspace not in target.resolve().parents:
            raise ValueError("Path escapes workspace")
        if operation in ("modify", "delete"):
            if relative not in allowed or not target.is_file():
                raise ValueError("Unauthorized existing-file operation: {}".format(relative))
        elif operation == "create":
            if target.exists() or not target.parent.is_dir():
                raise ValueError("New file must not exist and parent directory must exist")
        else:
            raise ValueError("Unknown file operation: {}".format(operation))
        content = edit.get("content")
        if operation != "delete":
            if not isinstance(content, str) or len(content) > 200000:
                raise ValueError("Invalid generated file content")
            compile(content, str(target), "exec")
        pending.append((relative, target, operation, content))
        seen.add(relative)
    backups = {}
    try:
        for relative, target, operation, content in pending:
            backups[relative] = target.read_bytes() if target.exists() else None
            if operation == "delete":
                target.unlink()
            else:
                target.write_text(content, encoding="utf-8")
    except OSError as original_error:
        # A write can fail after truncating its target. Restore that target too,
        # and keep restoring other files even if one restoration fails.
        rollback_errors = []
        for relative, target, _, _ in reversed(pending):
            if relative not in backups:
                continue
            previous = backups[relative]
            try:
                if previous is None:
                    target.unlink(missing_ok=True)
                else:
                    target.write_bytes(previous)
            except OSError as rollback_error:
                rollback_errors.append("{}: {}".format(relative, rollback_error))
        if rollback_errors:
            raise OSError(
                "Edit failed ({}); rollback incomplete for: {}".format(
                    original_error, "; ".join(rollback_errors))) from original_error
        raise
    return [relative for relative, _, _, _ in pending]


def run_tests(workspace, timeout=30):
    """Run discovered unittest cases; zero discovered tests is not success."""
    try:
        process = subprocess.run(
            [os.sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
            cwd=str(workspace), capture_output=True, text=True, timeout=timeout,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        output = (process.stdout + "\n" + process.stderr)[-7000:]
        import re
        match = re.search(r"Ran (\d+) tests? in", output)
        count = int(match.group(1)) if match else 0
        return {"passed": process.returncode == 0 and count > 0,
                "tests_run": count, "output": output if count else output + "\nNo tests discovered"}
    except subprocess.TimeoutExpired:
        return {"passed": False, "tests_run": 0,
                "output": "Tests timed out after {} seconds".format(timeout)}



def run_verification(workspace, spec, timeout=30):
    """Run independently authored unittest code in the workspace.

    The spec is a Python unittest source string provided by the evaluator,
    never generated by the coding agent. Not a sandbox.
    """
    if not isinstance(spec, str) or not spec.strip():
        raise ValueError("Verification must be a nonempty unittest source")
    tests_dir = Path(workspace) / "tests"
    tests_dir.mkdir(exist_ok=True)
    test_path = tests_dir / "test_codepilot_verification.py"
    test_path.write_text(spec, encoding="utf-8")
    try:
        return run_tests(workspace, timeout=timeout)
    finally:
        test_path.unlink(missing_ok=True)

TEST_SYSTEM = """You are an independent Python test engineer. Produce ONLY JSON:
{"tests":"COMPLETE Python unittest source"}.
Write behavioral tests of the requested feature, including edge cases and existing
behavior where relevant. Use standard-library unittest, no external dependencies,
no network, no subprocess, and no filesystem writes. Do not modify application code.
Do not invent additional requirements: if behavior is unspecified, avoid assertions that impose new contracts.
Your tests will be reviewed as fallible model-generated checks, not ground truth.
"""


def _validate_generated_test_source(source):
    """Validate test syntax and minimal unittest structure before execution."""
    import ast
    if not isinstance(source, str) or not source.strip() or len(source) > 40000:
        raise ValueError("Test generator returned no usable unittest source")
    try:
        tree = ast.parse(source)
    except SyntaxError as original_error:
        # Some models double-escape line breaks inside the JSON `tests` value.
        # Only try this repair when there are no real line breaks in the source.
        if "\\n" not in source or "\n" in source:
            raise original_error
        repaired = source.replace("\\r\\n", "\n").replace("\\n", "\n")
        tree = ast.parse(repaired)
        source = repaired
    forbidden = {"subprocess", "socket", "requests", "urllib", "shutil", "ctypes"}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = ([a.name for a in node.names] if isinstance(node, ast.Import)
                     else [node.module or ""])
            if any(name.split(".")[0] in forbidden for name in names):
                raise ValueError("Generated tests import a forbidden module")
    if not any(isinstance(n, ast.FunctionDef) and n.name.startswith("test_")
               for n in ast.walk(tree)):
        raise ValueError("Generated tests contain no test methods")
    return source


def generate_task_tests(task, repo_map, context, retries=2):
    """Generate and validate tests, asking for corrected source if malformed."""
    messages = [
        {"role": "system", "content": TEST_SYSTEM},
        {"role": "user", "content": "Task: {}\nRepository map:\n{}\nContext:\n{}".format(task, repo_map, context)},
    ]
    last_error = None
    for index in range(retries + 1):
        answer = ask_model(messages)
        try:
            raw = answer.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            parsed = json.loads(raw)
            source = parsed.get("tests") if isinstance(parsed, dict) else None
            return _validate_generated_test_source(source)
        except (ValueError, SyntaxError, TypeError, IndexError) as exc:
            last_error = exc
            if index < retries:
                messages.extend([
                    {"role": "assistant", "content": answer},
                    {"role": "user", "content": (
                        "Your generated test suite was invalid: {}. "
                        "Return ONLY a JSON object with a tests field containing "
                        "syntactically valid Python unittest source. Use actual newlines "
                        "in the Python source (JSON-escaped once, not twice)."
                    ).format(str(exc)[:300])},
                ])
    raise ValueError("Test generation failed after {} responses: {}".format(retries + 1, last_error))


def run_generated_tests(workspace, source, timeout=30):
    """Execute generated unittest suite in a disposable workspace (NOT a sandbox)."""
    tests_dir = Path(workspace) / "tests"
    tests_dir.mkdir(exist_ok=True)
    target = tests_dir / "test_codepilot_generated.py"
    if target.exists():
        raise ValueError("Reserved generated-test filename already exists")
    target.write_text(source, encoding="utf-8")
    try:
        result = run_tests(workspace, timeout=timeout)
        # At least one generated test must be discovered; test file may fail to import.
        if result["tests_run"] < 1:
            result["passed"] = False
        return result
    finally:
        target.unlink(missing_ok=True)


def _repair_feedback(record, limit=3000):
    """Build bounded, stage-aware feedback for the next implementation attempt.

    The independent verification result is feedback, never a replacement for
    final verification. Avoid feeding unrelated successful test output.
    """
    stage = record.get("failure_stage") or "unknown"
    category = record.get("failure_category") or "unknown"
    output = str(record.get("output", ""))
    if stage == "independent_verification" and record.get("verification_output"):
        output = str(record["verification_output"])
    elif stage == "generated_tests" and record.get("generated_tests_output"):
        output = str(record["generated_tests_output"])
    changed = record.get("changed_files", [])
    return ("Failure stage: {}\nFailure category: {}\nFiles changed: {}\n"
            "Failure details (truncated):\n{}").format(
                stage, category, ", ".join(changed) if changed else "none", output[-limit:])


def _counterfactual_repair_prompt(record):
    """Use observed failures to request a falsifiable alternative, not imagined evidence."""
    feedback = _repair_feedback(record)
    return (
        "Counterfactual repair. The previous implementation FAILED.\n"
        "Observed evidence (do not invent missing details):\n{}\n\n"
        "Before writing edits, reason internally about: (1) the likely root cause, "
        "(2) which specific alternative implementation would have avoided the "
        "observed failure, and (3) which existing test or verification would "
        "distinguish that alternative from the failed approach. Treat uncertain "
        "causes as hypotheses, not facts.\n"
        "Each retry starts from the ORIGINAL repository snapshot; no previous "
        "edits survive. Return a COMPLETE replacement batch with every required "
        "file, using create for files absent from the original snapshot. "
        "Return ONLY the specified JSON shape, with a concise reasoning_summary "
        "describing the hypothesis and alternative."
    ).format(feedback)


def run_agent(repo_path, task, attempts=2, max_files=6, test_timeout=30, verification=None, generate_tests=False, json_mode=None, retrieval_strategy="lexical", repair_feedback=True, repair_policy="standard" ):
    if repair_policy not in ("standard", "counterfactual"):
        raise ValueError("repair_policy must be standard or counterfactual")
    if not isinstance(repair_feedback, bool):
        raise ValueError("repair_feedback must be a boolean")
    if not 1 <= attempts <= 5:
        raise ValueError("attempts must be 1-5")
    original = Path(repo_path).expanduser().resolve()
    allowed = set(discover_python_files(original))
    if not allowed:
        raise ValueError("No Python files discovered")
    # Temporary copy, not a security sandbox. Run only trusted repositories.
    with tempfile.TemporaryDirectory(prefix="codepilot-") as temp:
        workspace = Path(temp) / "repo"
        shutil.copytree(str(original), str(workspace), ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__", "node_modules", ".env"), symlinks=False)
        repo_map = repository_map(workspace)
        context = retrieve_context(workspace, task, max_files, strategy=retrieval_strategy)
        generated_source = None
        generated_status = "disabled"
        if generate_tests:
            try:
                generated_source = generate_task_tests(task, repo_map, context)
                generated_status = "generated"
            except (ValueError, SyntaxError, json.JSONDecodeError, RuntimeError) as exc:
                generated_status = "generation_failed: {}".format(str(exc)[:500])
        if generate_tests and generated_source is None:
            return {"task": task, "success": False, "history": [], "files": {},
                    "generated_test_status": generated_status, "generated_test_source": None,
                    "warning": "Test generation failed; no code was changed."}
        messages = [{"role": "system", "content": SYSTEM},
                    {"role": "user", "content": "Task: {}\n\nRepository map:\n{}\n\nSelected source context:\n{}".format(task, repo_map, context)}]
        retrieval_metadata = {"strategy": retrieval_strategy, "context_chars": len(context),
                              "context_files": [line[4:] for line in context.splitlines() if line.startswith("### ")],
                              "repository_map_chars": len(repo_map)}
        history = []
        for attempt in range(1, attempts + 1):
            answer = ""
            started = time.monotonic()
            stage = "model_request"
            formatting = {}
            # Start each attempt from the original snapshot so failed edits do not accumulate.
            if attempt > 1:
                shutil.rmtree(workspace)
                shutil.copytree(str(original), str(workspace), ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__", "node_modules", ".env"), symlinks=False)
            try:
                answer = ask_model(messages, json_mode=json_mode)
                # Repair malformed JSON without consuming an implementation attempt.
                # This is a formatting retry, not a code/test retry.
                stage = "edit_json"
                parsed = parse_edits_with_format_retry(
                    messages,
                    answer,
                    format_retries=int(os.environ.get("CODEPILOT_FORMAT_RETRIES", "2")),
                    diagnostics=formatting,
                    json_mode=json_mode,
                )
                answer = parsed.pop("_validated_raw_answer")
                stage = "edit_validation"
                changed = apply_edits(workspace, parsed["edits"], allowed)
                stage = "smoke_tests"
                test_result = run_tests(workspace, timeout=test_timeout)
                test_result["smoke_tests_passed"] = test_result["passed"]
                test_result["smoke_tests_run"] = test_result["tests_run"]
                if test_result["passed"] and generated_source:
                    stage = "generated_tests"
                    generated_result = run_generated_tests(workspace, generated_source, test_timeout)
                    test_result["generated_tests_passed"] = generated_result["passed"]
                    test_result["generated_tests_run_total"] = generated_result["tests_run"]
                    test_result["generated_tests_output"] = generated_result["output"]
                    if not generated_result["passed"]:
                        test_result["passed"] = False
                        test_result["output"] += "\nGenerated task tests failed:\n" + generated_result["output"]
                if test_result["passed"] and verification:
                    stage = "independent_verification"
                    verification_result = run_verification(workspace, verification, test_timeout)
                    test_result["verification_passed"] = verification_result["passed"]
                    test_result["verification_output"] = verification_result["output"]
                    if not verification_result["passed"]:
                        test_result["passed"] = False
                        test_result["output"] += "\nTask verification failed:\n" + verification_result["output"]
                record = {"attempt": attempt, "changed_files": changed, "reasoning_summary": parsed.get("reasoning_summary", ""), **test_result}
                record["failure_stage"] = None if record["passed"] else stage
                record["failure_category"] = None if record["passed"] else "test_failure"
            except (ValueError, SyntaxError, KeyError, json.JSONDecodeError, OSError, LLMAPIError) as exc:
                record = {"attempt": attempt, "changed_files": [], "passed": False, "output": str(exc),
                          "failure_stage": stage,
                          "failure_category": ("provider_error" if isinstance(exc, LLMAPIError)
                                               else "malformed_edit_json" if stage == "edit_json"
                                               else "provider_error" if stage == "model_request"
                                               else "edit_validation_error" if stage == "edit_validation"
                                               else "execution_error")}
            record["repair_attempt"] = attempt > 1
            record["format_retries_used"] = formatting.get("format_retries_used", 0)
            record["format_repair_succeeded"] = formatting.get("format_repair_succeeded", False)
            record["elapsed_seconds"] = round(time.monotonic() - started, 3)
            history.append(record)
            if record["passed"]:
                break
            # Provider failures are infrastructure errors, not repairable code defects.
            if record["failure_category"] == "provider_error":
                break
            if repair_feedback:
                messages.extend([{"role": "assistant", "content": answer},
                                 {"role": "user", "content": (_counterfactual_repair_prompt(record) if repair_policy == "counterfactual" else "Tests/validation failed:\n{}\nIMPORTANT: Each retry starts from the ORIGINAL repository snapshot, not the previous attempt. Files created in a previous attempt do not exist now. Return a COMPLETE replacement edit batch: use operation=create for newly introduced files (even if created in the prior failed attempt), and operation=modify for files originally present. Include every file needed for the working feature, not just the file that failed. Return valid JSON only, with complete file contents.".format(_repair_feedback(record)))}])
            else:
                # A genuine fresh sample: no prior answer, test output, or failure label.
                # Keep the original task, map, and context unchanged across retries.
                messages = messages[:2]
        final_files = {p: (workspace / p).read_text(encoding="utf-8") if (workspace / p).exists() else None for p in history[-1]["changed_files"]}
        return {"task": task, "success": history[-1]["passed"], "history": history, "files": final_files,
                "generated_test_status": generated_status, "generated_test_source": generated_source,
                "retrieval": retrieval_metadata,
                "repair": {"feedback_enabled": repair_feedback, "policy": repair_policy, "attempted": len(history) > 1,
                           "recovered": len(history) > 1 and history[-1]["passed"],
                           "code_failures": sum(r.get("failure_category") == "test_failure" for r in history),
                           "provider_failures": sum(r.get("failure_category") == "provider_error" for r in history)},
                "warning": "Generated tests are fallible and run code; use only trusted repositories. Original repository was not modified."}
