"""Orchestrate generated repair alternatives and executable replay."""

from codepilot.counterfactual_replay import replay_alternatives
from codepilot.replay_generation import generate_replay_candidates


def evaluate_replay_strategy(
    repo_path,
    messages,
    candidate_count=2,
    test_timeout=30,
    json_mode=None,
    public_verifier=None,
    temperature=None,
    prompt_condition=None,
):
    """Generate, execute, and select alternative repair candidates.

    Only public tests are used for candidate selection.
    Independent verification belongs outside this selection process.
    """
    generation = generate_replay_candidates(
        messages=messages,
        candidate_count=candidate_count,
        json_mode=json_mode,
        temperature=temperature,
        prompt_condition=prompt_condition,
    )

    replay = replay_alternatives(
        repo_path=repo_path,
        candidates=generation["candidates"],
        test_timeout=test_timeout,
        public_verifier=public_verifier,
    )

    selected_index = replay["selection"]["selected_index"]

    return {
        "selected_index": selected_index,
        "selected_edits": (
            generation["candidates"][selected_index]
            if selected_index is not None
            else None
        ),
        "candidates": generation["candidates"],
        "generation_records": generation["generation_records"],
        "replay_results": replay["results"],
        "selection": replay["selection"],
        "model_requests": generation["model_requests"],
        "test_executions": replay["test_executions"],
    }
