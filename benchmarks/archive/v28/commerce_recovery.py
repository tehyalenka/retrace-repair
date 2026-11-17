"""Six-module commerce benchmark using real LLM execution."""

import argparse
import json
from pathlib import Path
from unittest.mock import patch

import benchmarks.v18.record_replay as record_replay
import benchmarks.v22.natural_recovery as v22

HERE = Path(__file__).resolve().parent
CASES = ("commerce",)

ORIGINAL_SETUP = record_replay.task_setup


def setup(mode, case, temp):
    if case not in CASES:
        raise ValueError("Unknown commerce case: " + str(case))

    if mode == "offline":
        return ORIGINAL_SETUP(mode, "bugfix", temp)

    tasks = json.loads((HERE / "tasks.json").read_text())

    return (
        HERE / "cases" / case,
        tasks[case],
        (HERE / "hidden" / (case + ".py")).read_text(),
    )


def evaluate(**kwargs):
    with (
        patch.object(record_replay, "task_setup", side_effect=setup),
        patch.object(v22, "task_setup", side_effect=setup),
        patch.object(v22, "CASES", CASES),
    ):
        return v22.evaluate(
            capture_fn=record_replay.capture,
            **kwargs,
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode", choices=("live", "offline"), default="live"
    )
    parser.add_argument(
        "--cases", nargs="+", choices=CASES, default=list(CASES)
    )
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--cooldown", type=float, default=90)
    parser.add_argument(
        "--output", default="v28-live-commerce.json"
    )
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    result = evaluate(
        mode=args.mode,
        cases=args.cases,
        repeats=args.repeats,
        attempts=args.attempts,
        cooldown=args.cooldown,
        output=Path(args.output),
        resume=args.resume,
    )

    print(json.dumps(result.get("summary", {}), indent=2))
    print("Status:", result.get("status"))


if __name__ == "__main__":
    main()
