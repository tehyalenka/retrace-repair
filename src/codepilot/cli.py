import argparse
import json
import os
from pathlib import Path

from .repository_analyzer import index_repository, retrieve_context, repository_map
from .agent import run_agent


def main():
    parser = argparse.ArgumentParser(prog="codepilot", description="CodePilot-X repository-aware coding agent")
    sub = parser.add_subparsers(dest="command", required=True)
    p_index = sub.add_parser("index", help="Inspect Python source structure")
    p_index.add_argument("repository")
    p_map = sub.add_parser("map", help="Show repository module and symbol map")
    p_map.add_argument("repository")
    p_search = sub.add_parser("search", help="Retrieve code context")
    p_search.add_argument("repository")
    p_search.add_argument("task")
    p_agent = sub.add_parser("agent", help="Generate and test edits in a temporary copy")
    p_agent.add_argument("repository")
    p_agent.add_argument("task")
    p_agent.add_argument("--attempts", type=int, default=2)
    p_agent.add_argument("--generate-tests", action="store_true", help="Generate task-specific unittest checks before coding (experimental)")
    p_agent.add_argument("--output", default="codepilot-result.json")
    args = parser.parse_args()
    if args.command == "index":
        print(json.dumps(index_repository(args.repository), indent=2))
    elif args.command == "map":
        print(repository_map(args.repository))
    elif args.command == "search":
        print(retrieve_context(args.repository, args.task))
    else:
        if not 1 <= args.attempts <= 5:
            parser.error("--attempts must be between 1 and 5")
        result = run_agent(args.repository, args.task, attempts=args.attempts, generate_tests=args.generate_tests)
        target = Path(args.output)
        target.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print("Success: {} | Attempts: {} | Saved: {}".format(result["success"], len(result["history"]), target))
        print("Original repository was NOT changed. Review the JSON output before applying edits.")


if __name__ == "__main__":
    main()
