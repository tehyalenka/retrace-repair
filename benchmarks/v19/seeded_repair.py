"""Controlled seeded-failure paired repair benchmark; run with -m from repository root.

A seed is an intentionally defective implementation, NOT a model-generated error.
Only continuation calls in live mode are fresh LLM completions.
"""
import argparse
import json
import re
import tempfile
from pathlib import Path
from unittest.mock import patch

from benchmarks.v18.record_replay import task_setup, fingerprint

import codepilot.agent as agent

def _edit(source, path):
    return json.dumps({"edits": [{"path": path, "operation": "modify", "content": source}]})

SEEDS = {
    "bugfix": ("bookings.py", """from seats import Seats
from ledger import Ledger

class BookingService:
    def __init__(self, capacity):
        self.seats = Seats(capacity)
        self.ledger = Ledger()
        self.bookings = {}
        self.next_id = 1

    def book(self, event, customer, seats):
        self.seats.reserve(event, seats)
        booking_id = self.next_id
        self.next_id += 1
        self.bookings[booking_id] = (event, customer, seats)
        self.ledger.charge(booking_id, seats * 25)
        return booking_id

    def cancel(self, booking_id):
        booking = self.bookings.get(booking_id)
        if not booking:
            return False
        event, customer, seats = booking
        self.seats.release(event, seats)
        self.ledger.refund(booking_id, seats * 25)
        return True
"""),
    "feature": ("bank.py", """from accounts import Accounts
from transfers import transfer

class Bank:
    def __init__(self, balances):
        self.accounts = Accounts(balances)

    def balance(self, account_id):
        return self.accounts.balance(account_id)

    def transfer(self, source, destination, amount):
        transfer(self.accounts.balances, source, destination, amount)

    def transfer_many(self, transfers):
        for source, destination, amount in transfers:
            transfer(self.accounts.balances, source, destination, amount)
        return dict(self.accounts.balances)
"""),
    "refactor": ("search.py", """from index import build_index, find_matches

def search_documents(query, documents, case_insensitive=False):
    if not case_insensitive:
        return find_matches(build_index(documents), query)
    return [doc['id'] for doc in documents if query.lower() in doc['text'].lower()]
"""),
}


def safe_feedback(record, limit=3000):
    """Disclose failed test identifiers, never hidden verifier source or assertions."""
    output = record.get("verification_output") or record.get("output") or ""
    failed = re.findall(r"^([^\n]+?) \.\.\. (?:FAIL|ERROR)$", output, re.MULTILINE)
    if not failed:
        failed = re.findall(r"^(?:FAIL|ERROR): ([^\n]+)", output, re.MULTILINE)
    names = ", ".join(failed[:12]) if failed else "Verification failed (details withheld)"
    return "Failure stage: {}\nFailure category: {}\nFailed tests: {}\nHidden test code and assertions withheld.".format(
        record.get("failure_stage"), record.get("failure_category"), names)[:limit]


def run_case(case, offline=False, attempts=3, condition_order=("resample", "feedback")):
    if case not in SEEDS:
        raise ValueError("Unknown seeded case: " + case)
    with tempfile.TemporaryDirectory() as temp:
        repo, task, verifier = task_setup("live", case, temp)
        path, defective = SEEDS[case]
        seed = _edit(defective, path=path)
        correct = None
        if offline:
            if case == "bugfix":
                correct = defective.replace("booking = self.bookings.get(booking_id)", "booking = self.bookings.pop(booking_id, None)")
            elif case == "feature":
                correct = defective.replace("        for source, destination, amount in transfers:\n            transfer(self.accounts.balances, source, destination, amount)\n        return dict(self.accounts.balances)", "        staged = dict(self.accounts.balances)\n        for source, destination, amount in transfers:\n            transfer(staged, source, destination, amount)\n        self.accounts.balances = staged\n        return dict(staged)")
            else:
                correct = defective.replace("query.lower() in doc['text'].lower()", "query.casefold() in doc['text'].casefold()")
        rows = []
        real_ask = agent.ask_model
        if not condition_order or len(set(condition_order)) != len(condition_order) or not set(condition_order).issubset({"feedback", "resample"}):
            raise ValueError("condition_order must contain one or both unique supported conditions")
        for condition in condition_order:
            feedback = condition == "feedback"
            calls = []
            def ask(messages, **kwargs):
                if not calls:
                    answer, origin = seed, "seeded_defect"
                elif offline:
                    answer, origin = _edit(correct, path=path), "scripted_correction"
                else:
                    answer, origin = real_ask(messages, **kwargs), "fresh_model_completion"
                calls.append({"origin": origin, "response": answer,
                              "feedback_message_present": any("Tests/validation failed:" in m.get("content", "") for m in messages)})
                return answer
            with patch.object(agent, "ask_model", side_effect=ask), patch.object(agent, "_repair_feedback", side_effect=safe_feedback):
                result = agent.run_agent(repo, task, attempts=attempts, verification=verifier, repair_feedback=feedback)
            history = result.get("history", [])
            if not history or history[0].get("failure_category") != "test_failure":
                raise RuntimeError("Seed failed to produce a test failure for " + case)
            rows.append({"condition": condition, "feedback_enabled": feedback,
                         "success": result["success"], "history": history,
                         "model_calls": calls,
                         "fresh_model_calls": sum(c["origin"] == "fresh_model_completion" for c in calls),
                         "provider_failure": any(h.get("failure_category") == "provider_error" for h in history)})
        return {"schema": 1, "evaluation": "seeded_failure", "case": case,
                "mode": "offline" if offline else "live", "attempts": attempts,
                "repo_sha256": fingerprint(repo), "seeded_file": path,
                "same_initial_defect": True, "sanitized_feedback": True, "rows": rows,
                "limitations": ["Seeded defects are not naturally model-generated errors",
                                "Offline corrections are scripted and not evidence of LLM repair",
                                "Failed-test identifiers are supplied only to the feedback arm",
                                "A small sample cannot establish a statistically reliable feedback advantage"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("offline", "live"), default="offline")
    parser.add_argument("--cases", nargs="+", choices=sorted(SEEDS), default=sorted(SEEDS))
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--output", default="v19-seeded-results.json")
    args = parser.parse_args()
    if args.attempts < 2:
        parser.error("--attempts must be at least 2")
    report = {"schema": 1, "evaluation": "seeded_failure", "mode": args.mode, "cases": [], "errors": []}
    for case in args.cases:
        try:
            result = run_case(case, offline=args.mode == "offline", attempts=args.attempts)
            report["cases"].append(result)
            print("{}: {}".format(case, ", ".join("{}={}".format(r["condition"], r["success"]) for r in result["rows"])), flush=True)
        except Exception as exc:
            report["errors"].append({"case": case, "error_type": type(exc).__name__, "message": str(exc)})
            print("{}: error {}".format(case, type(exc).__name__), flush=True)
        finally:
            Path(args.output).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("Saved:", args.output)


if __name__ == "__main__":
    main()
