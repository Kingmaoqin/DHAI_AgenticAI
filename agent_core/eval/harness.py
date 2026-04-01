from __future__ import annotations

from dataclasses import asdict

from agent_core import build_default_runner


def run_query(query: str) -> dict:
    runner = build_default_runner()
    run_state = runner.run(query=query)
    return {
        "task_id": run_state.task_spec.task_id,
        "family": run_state.task_spec.family,
        "policy": run_state.selected_policy,
        "final_response": asdict(run_state.final_response),
        "trace_len": len(run_state.trace),
    }
