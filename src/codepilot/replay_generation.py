"""Generate alternative repair candidates for executable replay."""

import os

from codepilot import agent as agent_module
from codepilot.agent import parse_edits_with_format_retry


def generate_replay_candidates(
    messages,
    candidate_count=2,
    json_mode=None,
    temperature=None,
    prompt_condition=None,
):
    """Generate independently prompted candidate edit batches.

    Each candidate starts with the same conversation context.
    This function does not execute tests or select candidates.
    """
    if not 1 <= candidate_count <= 5:
        raise ValueError("candidate_count must be between 1 and 5")

    if prompt_condition is None:
        prompt_condition = os.environ.get("CODEPILOT_REPLAY_PROMPT_CONDITION", "invariant")

    if temperature is None:
        if "CODEPILOT_REPLAY_TEMPERATURE" in os.environ:
            temperature = float(os.environ["CODEPILOT_REPLAY_TEMPERATURE"])
        elif candidate_count > 1 and "CODEPILOT_TEMPERATURE" not in os.environ:
            temperature = 0.7
        else:
            temperature = float(os.environ.get("CODEPILOT_TEMPERATURE", "0"))

    candidates = []
    generation_records = []

    for index in range(candidate_count):
        candidate_messages = [
            dict(message) for message in messages
        ]

        if prompt_condition == "standard":
            candidate_instruction = (
                "Generate repair candidate {} of {}. "
                "Produce one complete, independently applicable edit batch. "
                "Ensure rigorous enterprise contract safety: strict type checks "
                "(explicitly reject booleans where numbers/integers are expected), "
                "full rollback on write failures or trigger aborts, idempotency "
                "conflict verification, and fail-closed tenant boundaries. "
                "Consider alternative implementation choices while satisfying "
                "the original task and test requirements. "
                "Return only the required JSON response."
            ).format(index + 1, candidate_count)
        else:
            candidate_instruction = (
                "Generate repair candidate {} of {}. "
                "Produce one complete, independently applicable edit batch.\n\n"
                "MANDATORY INVARIANT CONTRACTS (RETRACE v2.0 Specification):\n"
                "1. ENTRYPOINT ARGUMENT VALIDATION: Immediately validate all inputs at public function and method "
                "entrypoints. Raise ValueError or TypeError on invalid, negative, non-callable, empty, or mismatched types "
                "(strictly reject `bool` for numeric integer/float parameters). Do not initialize or mutate state if inputs are invalid.\n"
                "2. STATE MACHINE CONSERVATION: Never silence test assertions by prematurely wiping failure counts, "
                "clearing retry state, or bypassing half-open probation limits. In probation/half-open states, "
                "any probation failure must immediately transition back to the OPEN state. In saga orchestrators, "
                "compensation actions must execute in strict reverse order of execution.\n"
                "3. ATOMICITY & ZERO SWALLOWED EXCEPTIONS: Wrap mutations in atomic transactions with complete rollback "
                "on write failures or trigger aborts. Never swallow exceptions with `except: pass` or return None on failure.\n"
                "4. FAIL-CLOSED BOUNDARIES: Enforce idempotency key conflict checks and fail-closed tenant isolation.\n\n"
                "Consider alternative implementation choices while satisfying the original task and test requirements. "
                "Return only the required JSON response."
            ).format(index + 1, candidate_count)

        if candidate_messages and candidate_messages[-1].get("role") == "user":
            candidate_messages[-1] = {
                "role": "user",
                "content": candidate_messages[-1]["content"] + "\n\n" + candidate_instruction,
            }
        else:
            candidate_messages.append({
                "role": "user",
                "content": candidate_instruction,
            })

        diagnostics = {}
        try:
            answer = agent_module.ask_model(
                candidate_messages,
                json_mode=json_mode,
                temperature=temperature,
            )

            parsed = parse_edits_with_format_retry(
                candidate_messages,
                answer,
                format_retries=int(
                    os.environ.get("CODEPILOT_FORMAT_RETRIES", "2")
                ),
                diagnostics=diagnostics,
                json_mode=json_mode,
            )
        except Exception as exc:
            if candidates:
                # If at least one candidate succeeded, proceed with available candidates
                break
            if index + 1 < candidate_count:
                continue
            raise exc

        candidates.append(parsed["edits"])

        generation_records.append({
            "candidate_index": index,
            "raw_answer": answer,
            "reasoning_summary": parsed.get(
                "reasoning_summary", ""
            ),
            "format_retries_used": diagnostics.get(
                "format_retries_used", 0
            ),
        })

    return {
        "candidates": candidates,
        "generation_records": generation_records,
        "candidate_count": len(candidates),
        "model_requests": sum(
            1 + record["format_retries_used"]
            for record in generation_records
        ),
    }
