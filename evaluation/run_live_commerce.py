import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path

from codepilot.agent import run_agent
from backend.run_artifacts import save_run_artifacts

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT / "evaluation" / "multifile-commerce"

TASK = """
Implement the unfinished commerce workflow across inventory.py,
pricing.py, and orders.py.

Requirements:
- reserve(product, quantity) must validate the product and quantity,
  check available stock, and decrement inventory only on success.
- calculate_total(product, quantity) must return unit price multiplied
  by quantity, rejecting unknown products and invalid quantities.
- create_order(product, quantity) must return a dictionary containing
  product, quantity, and total.
- Reject zero, negative, boolean, and non-integer quantities.
- Reject unknown products and insufficient stock with ValueError.
- Failed orders must not change inventory.
- Preserve existing public function signatures and constants.
- Modify all necessary modules; do not modify test files.
"""

def main():
    run_id = secrets.token_hex(6)
    verification = (
        REPO / "independent_tests" / "test_edge_cases.py"
    ).read_text(encoding="utf-8")

    provider = os.environ.get("CODEPILOT_PROVIDER", "groq")
    model = os.environ.get(
        "CODEPILOT_MODEL", "openai/gpt-oss-120b"
    )

    print("Run ID:", run_id, flush=True)
    print("Provider:", provider, flush=True)
    print("Model:", model, flush=True)
    print("Attempts: 1", flush=True)
    print("Starting autonomous evaluation...", flush=True)

    result = run_agent(
        str(REPO),
        TASK,
        attempts=1,
        max_files=6,
        test_timeout=30,
        verification=verification,
        generate_tests=False,
    )

    run = {
        "id": run_id,
        "repository": str(REPO),
        "task": TASK,
        "status": "completed" if result["success"] else "failed",
        "provider": provider,
        "model": model,
        "result": result,
        "execution_provenance": {
            "source": "codepilot_agent",
            "execution_mode": "autonomous",
            "recorded_at_creation": True,
        },
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }

    checkpoint = ROOT / ".codepilot-runs" / run_id
    checkpoint.mkdir(parents=True, exist_ok=True)

    checkpoint_file = checkpoint / "agent_result_checkpoint.json"

    checkpoint_file.write_text(
        json.dumps(run, indent=2, default=str),
        encoding="utf-8",
    )

    print("Checkpoint saved:", checkpoint_file, flush=True)

    save_run_artifacts(ROOT, run)

    print("\n=== AUTONOMOUS RESULT ===")
    print("Run ID:", run_id)
    print("Success:", result["success"])
    print("Attempts:", len(result["history"]))
    print("Changed files:", list(result.get("files", {})))

    for record in result["history"]:
        print("Smoke passed:", record.get("smoke_tests_passed"))
        print("Smoke count:", record.get("smoke_tests_run"))
        print("Verification passed:", record.get("verification_passed"))
        print("Failure stage:", record.get("failure_stage"))
        print("Failure category:", record.get("failure_category"))
        print("Output:", str(record.get("output", ""))[-1500:])
        print(
            "Verification output:",
            str(record.get("verification_output", ""))[-1500:]
        )

    print("Artifacts:", ROOT / ".codepilot-runs" / run_id)

if __name__ == "__main__":
    main()
