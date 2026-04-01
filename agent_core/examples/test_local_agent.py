from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from dataclasses import asdict
from pathlib import Path

from agent_core import build_default_runner
from agent_core.core.parser import TaskParser
from agent_core.policies.builtin import MixedAnalysisPolicy
from agent_core.services.llm_client import OpenAICompatibleLLMClient


DEFAULT_QUERY = (
    "Based on the office handbook, what is the lunch reimbursement limit, "
    "and what is 18 + 24? Return a short report with evidence."
)


def check_health(endpoint: str) -> dict:
    try:
        with urllib.request.urlopen(f"{endpoint.rstrip('/')}/health", timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code in {404, 405}:
            return {
                "status": "unknown",
                "model_loaded": "unknown",
                "note": "No /health endpoint; assuming an OpenAI-compatible API.",
            }
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", default=os.getenv("LOCAL_LLM_ENDPOINT", "http://127.0.0.1:8080"))
    parser.add_argument("--query", default=DEFAULT_QUERY)
    parser.add_argument("--output-dir", default="/home/xqin5/agenticAI/runs")
    parser.add_argument("--debug-llm", action="store_true")
    args = parser.parse_args()

    print(f"Checking local LLM endpoint: {args.endpoint}")
    try:
        health = check_health(args.endpoint)
    except urllib.error.URLError as exc:
        raise SystemExit(f"Failed to reach local LLM endpoint: {exc}") from exc

    print("Health check:")
    print(json.dumps(health, indent=2, ensure_ascii=True))

    if args.debug_llm:
        print_debug_responses(endpoint=args.endpoint, query=args.query)

    os.environ["LOCAL_LLM_ENDPOINT"] = args.endpoint
    runner = build_default_runner()
    output_dir = Path(args.output_dir)
    run_state = runner.run(query=args.query, output_dir=output_dir)

    print("\nRun summary:")
    print(f"run_id: {run_state.run_id}")
    print(f"policy: {run_state.selected_policy}")
    print(f"planning_mode: {run_state.planning_mode}")
    print(f"trace_events: {len(run_state.trace)}")

    print("\nPlan execution:")
    for step in run_state.plan:
        print(
            json.dumps(
                {
                    "step_id": step.step_id,
                    "goal": step.goal,
                    "selected_skill": step.selected_skill,
                    "routing_mode": step.metadata.get("routing_mode"),
                    "routing_reason": step.metadata.get("routing_reason"),
                    "status": step.status,
                },
                ensure_ascii=True,
            )
        )

    print("\nFinal response:")
    print(json.dumps(asdict(run_state.final_response), indent=2, ensure_ascii=True))

    print("\nSaved files:")
    print(output_dir / f"{run_state.run_id}_state.json")
    print(output_dir / f"{run_state.run_id}_trace.json")


def print_debug_responses(endpoint: str, query: str) -> None:
    client = OpenAICompatibleLLMClient(base_url=endpoint)
    task = TaskParser().parse(query)
    fallback_plan = MixedAnalysisPolicy().build_plan(task)

    plan_payload = {
        "task_id": task.task_id,
        "query": task.raw_query,
        "family": task.family,
        "domain": task.domain,
        "constraints": task.constraints,
        "output_schema": task.output_schema,
        "fallback_policy": "mixed_analysis",
        "fallback_plan": [
            {
                "step_id": step.step_id,
                "goal": step.goal,
                "inputs_needed": step.inputs_needed,
                "candidate_skills": step.candidate_skills,
                "expected_artifact": step.expected_artifact,
            }
            for step in fallback_plan
        ],
        "available_skills": [
            {"name": "llm_query_parser", "description": "Local-LLM parser that converts the raw query into structured task slots.", "supported_artifacts": ["parsed_query"]},
            {"name": "parser", "description": "Rule-based parser that extracts retrieval text and arithmetic expressions from the raw query.", "supported_artifacts": ["parsed_query"]},
            {"name": "retrieval", "description": "Keyword retrieval over the built-in mock handbook documents.", "supported_artifacts": ["retrieval_result"]},
            {"name": "calculator", "description": "Deterministic arithmetic evaluator for simple expressions.", "supported_artifacts": ["calculation_result"]},
            {"name": "llm_report_writer", "description": "Local-LLM report writer that converts retrieved evidence and calculations into final JSON.", "supported_artifacts": ["report"]},
            {"name": "report_writer", "description": "Template-based deterministic report writer.", "supported_artifacts": ["report"]},
        ],
    }
    planner_messages = [
        {
            "role": "system",
            "content": (
                "You are a workflow planner for an agentic system. "
                "Return strict JSON with a single key named steps. "
                "Each step must contain step_id, goal, inputs_needed, candidate_skills, expected_artifact. "
                "Use only available skills. The first step must create parsed_query. "
                "The last step must create report. Keep the plan short. Do not add markdown fences."
            ),
        },
        {"role": "user", "content": json.dumps(plan_payload, ensure_ascii=True)},
    ]
    planner_raw = client.chat_completion(planner_messages, max_tokens=500, temperature=0.1)
    print("\nPlanner raw output:")
    print(planner_raw)

    router_payload = {
        "query": query,
        "family": task.family,
        "current_step": {
            "step_id": "step-1",
            "goal": "Parse the user query into structured slots.",
            "expected_artifact": "parsed_query",
            "inputs_needed": ["task_spec.raw_query"],
        },
        "available_artifacts": [],
        "candidate_skills": [
            {"name": "llm_query_parser", "description": "Local-LLM parser that converts the raw query into structured task slots.", "supported_artifacts": ["parsed_query"]},
            {"name": "parser", "description": "Rule-based parser that extracts retrieval text and arithmetic expressions from the raw query.", "supported_artifacts": ["parsed_query"]},
        ],
    }
    router_messages = [
        {
            "role": "system",
            "content": (
                "You are a workflow router for an agentic system. "
                "Return strict JSON with keys selected_skill and reason. "
                "Pick exactly one name from candidate_skills. "
                "selected_skill must exactly match one candidate name. Do not add markdown fences."
            ),
        },
        {"role": "user", "content": json.dumps(router_payload, ensure_ascii=True)},
    ]
    router_raw = client.chat_completion(router_messages, max_tokens=180, temperature=0.1)
    print("\nRouter raw output:")
    print(router_raw)


if __name__ == "__main__":
    main()
