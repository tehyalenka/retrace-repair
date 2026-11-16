"""Public-feedback capture and paired evaluation with post-repair heldout tests.

Only trusted test sources should be used. This is NOT a sandbox.
Never publish traces without reviewing prompts and generated code.
"""
import argparse
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from benchmarks.v18 import record_replay
from benchmarks.v18 import checkpointed_three_arm


def _read_verifier(path):
    source = Path(path).read_text(encoding="utf-8")
    if not source.strip():
        raise ValueError("Empty verifier")
    return source


def _sources(public_path, heldout_path):
    public = _read_verifier(public_path)
    heldout = _read_verifier(heldout_path)
    if public == heldout:
        raise ValueError("Public and heldout verifiers must differ")
    return public, heldout


def _public_setup(public):
    original = record_replay.task_setup
    def setup(mode, case, temp):
        repo, task, _ = original(mode, case, temp)
        return repo, task, public
    return setup


def capture(mode, case, output, public_path, heldout_path):
    public, _ = _sources(public_path, heldout_path)
    with patch.object(record_replay, "task_setup", side_effect=_public_setup(public)):
        trace = record_replay.capture(mode, case, output)
    if trace.get("first_attempt", {}).get("failure_category") != "test_failure":
        raise ValueError("Initial edit must fail public verification; capture a different failure")
    return trace


def evaluate(trace_path, output, public_path, heldout_path, offline=False, repetitions=1, attempts=3):
    public, heldout = _sources(public_path, heldout_path)
    trace = json.loads(Path(trace_path).read_text(encoding="utf-8"))
    public_digest = hashlib.sha256(public.encode("utf-8")).hexdigest()
    if trace.get("verifier_sha256") != public_digest:
        raise ValueError("Trace was not captured with this public verifier")
    with patch.object(record_replay, "task_setup", side_effect=_public_setup(public)):
        return checkpointed_three_arm.evaluate(trace_path, output, offline=offline,
                                               repetitions=repetitions, attempts=attempts,
                                               heldout_verification=heldout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("capture", "evaluate"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--public-verifier", required=True)
        cmd.add_argument("--heldout-verifier", required=True)
        cmd.add_argument("--output", required=True)
        if name == "capture":
            cmd.add_argument("--mode", choices=("offline", "live"), default="offline")
            cmd.add_argument("--case", choices=("bugfix", "feature", "refactor"), default="bugfix")
        else:
            cmd.add_argument("--trace", required=True)
            cmd.add_argument("--offline", action="store_true")
            cmd.add_argument("--repetitions", type=int, default=1)
            cmd.add_argument("--attempts", type=int, default=3)
    args = parser.parse_args()
    if args.command == "capture":
        result = capture(args.mode, args.case, args.output, args.public_verifier, args.heldout_verifier)
        print("Captured public failure:", result["first_attempt"]["failure_category"])
    else:
        result = evaluate(args.trace, args.output, args.public_verifier, args.heldout_verifier,
                          offline=args.offline, repetitions=args.repetitions, attempts=args.attempts)
        for row in result["rows"]:
            print(row["key"], "public=", row["success"], "heldout=", row["heldout"]["passed"])
    print("Saved:", args.output)


if __name__ == "__main__":
    main()
