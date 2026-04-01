from __future__ import annotations

import json
import re

from agent_core.policies.base import TaskPolicy
from agent_core.schemas import PlanStep, TaskSpec
from agent_core.services.llm_client import OpenAICompatibleLLMClient, extract_json_object
from agent_core.skills.registry import SkillRegistry


class Planner:
    def __init__(self, registry: SkillRegistry, llm_client: OpenAICompatibleLLMClient | None = None) -> None:
        self.registry = registry
        self.llm_client = llm_client

    def build_plan(self, task_spec: TaskSpec, fallback_policy: TaskPolicy) -> tuple[list[PlanStep], str]:
        fallback_plan = fallback_policy.build_plan(task_spec)
        if self.llm_client is None or not self.llm_client.is_healthy():
            return fallback_plan, "rule"

        try:
            plan = self._build_with_llm(task_spec=task_spec, fallback_plan=fallback_plan, policy_name=fallback_policy.name)
            return plan, "llm"
        except Exception:
            return fallback_plan, "rule_fallback"

    def _build_with_llm(
        self,
        task_spec: TaskSpec,
        fallback_plan: list[PlanStep],
        policy_name: str,
    ) -> list[PlanStep]:
        simple_plan = self._build_with_simple_llm_sequence(task_spec=task_spec)
        if simple_plan:
            return simple_plan

        plan_payload = {
            "task_id": task_spec.task_id,
            "query": task_spec.raw_query,
            "family": task_spec.family,
            "domain": task_spec.domain,
            "constraints": task_spec.constraints,
            "output_schema": task_spec.output_schema,
            "fallback_policy": policy_name,
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
            "available_skills": self.registry.metadata(),
        }
        messages = [
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

        payload = self._request_plan_payload(messages=messages)
        return self._validate_steps(payload.get("steps"), fallback_plan=fallback_plan)

    def _build_with_simple_llm_sequence(self, task_spec: TaskSpec) -> list[PlanStep] | None:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a planning classifier. "
                    "Choose the ordered artifact sequence needed to answer the query. "
                    "Valid artifact names are: parsed_query, retrieval_result, calculation_result, report. "
                    "Rules: always start with parsed_query and end with report. "
                    "Include retrieval_result only if the query requires policy/document/evidence lookup. "
                    "Include calculation_result only if the query includes arithmetic or numeric computation. "
                    "Reply with only the artifact names separated by commas. "
                    "Example: parsed_query,retrieval_result,report"
                ),
            },
            {"role": "user", "content": task_spec.raw_query},
        ]
        raw = self.llm_client.chat_completion(messages=messages, max_tokens=60, temperature=0.0)
        sequence = self._extract_artifact_sequence(raw)
        if not sequence:
            return None

        step_templates = {
            "parsed_query": {
                "goal": "Parse the user query into structured slots.",
                "inputs_needed": ["task_spec.raw_query"],
                "candidate_skills": ["llm_query_parser", "parser"],
            },
            "retrieval_result": {
                "goal": "Retrieve the relevant policy evidence.",
                "inputs_needed": ["artifact:parsed_query"],
                "candidate_skills": ["retrieval"],
            },
            "calculation_result": {
                "goal": "Compute the requested arithmetic expression.",
                "inputs_needed": ["artifact:parsed_query"],
                "candidate_skills": ["calculator"],
            },
            "report": {
                "goal": "Write a final structured response.",
                "inputs_needed": ["artifact:retrieval_result", "artifact:calculation_result"],
                "candidate_skills": ["llm_report_writer", "report_writer"],
            },
        }
        return [
            PlanStep(
                step_id=f"step-{index}",
                goal=step_templates[artifact]["goal"],
                inputs_needed=step_templates[artifact]["inputs_needed"],
                candidate_skills=step_templates[artifact]["candidate_skills"],
                expected_artifact=artifact,
                metadata={"planner_source": "llm_sequence"},
            )
            for index, artifact in enumerate(sequence, start=1)
        ]

    def _request_plan_payload(self, messages: list[dict[str, str]]) -> dict[str, object]:
        raw = self.llm_client.chat_completion(messages=messages, max_tokens=500, temperature=0.1)
        try:
            payload = extract_json_object(raw)
            if "steps" in payload:
                return payload
            if isinstance(payload.get("plan"), list):
                return {"steps": payload["plan"]}
        except Exception:
            pass

        recovered_steps = self._recover_steps_from_text(raw)
        if recovered_steps:
            return {"steps": recovered_steps}

        repair_messages = [
            {
                "role": "system",
                "content": (
                    "Convert the provided planning output into strict JSON. "
                    "Return only one JSON object with key steps. "
                    "Each element in steps must contain step_id, goal, inputs_needed, candidate_skills, expected_artifact."
                ),
            },
            {"role": "user", "content": raw},
        ]
        repaired_raw = self.llm_client.chat_completion(messages=repair_messages, max_tokens=500, temperature=0.0)
        payload = extract_json_object(repaired_raw)
        if "steps" in payload:
            return payload
        if isinstance(payload.get("plan"), list):
            return {"steps": payload["plan"]}
        recovered_steps = self._recover_steps_from_text(repaired_raw)
        if recovered_steps:
            return {"steps": recovered_steps}
        raise ValueError("planner could not obtain structured steps")

    def _recover_steps_from_text(self, raw: str) -> list[dict[str, object]]:
        lowered = raw.lower()
        recovered: list[dict[str, object]] = []

        if any(token in lowered for token in ("parse", "parser", "structured slots")):
            recovered.append(
                {
                    "step_id": "step-1",
                    "goal": "Parse the user query into structured slots.",
                    "inputs_needed": ["task_spec.raw_query"],
                    "candidate_skills": ["llm_query_parser", "parser"],
                    "expected_artifact": "parsed_query",
                }
            )
        if any(token in lowered for token in ("retrieval", "retrieve", "evidence", "handbook", "policy")):
            recovered.append(
                {
                    "step_id": f"step-{len(recovered) + 1}",
                    "goal": "Retrieve the relevant policy evidence.",
                    "inputs_needed": ["artifact:parsed_query"],
                    "candidate_skills": ["retrieval"],
                    "expected_artifact": "retrieval_result",
                }
            )
        if any(token in lowered for token in ("calculate", "calculation", "arithmetic", "compute")):
            recovered.append(
                {
                    "step_id": f"step-{len(recovered) + 1}",
                    "goal": "Compute the requested arithmetic expression.",
                    "inputs_needed": ["artifact:parsed_query"],
                    "candidate_skills": ["calculator"],
                    "expected_artifact": "calculation_result",
                }
            )
        if any(token in lowered for token in ("report", "final response", "summary", "answer")):
            recovered.append(
                {
                    "step_id": f"step-{len(recovered) + 1}",
                    "goal": "Write a final structured response.",
                    "inputs_needed": ["artifact:retrieval_result", "artifact:calculation_result"],
                    "candidate_skills": ["llm_report_writer", "report_writer"],
                    "expected_artifact": "report",
                }
            )

        # Remove duplicates while preserving order by expected artifact.
        deduped: list[dict[str, object]] = []
        seen_artifacts: set[str] = set()
        for step in recovered:
            artifact = step["expected_artifact"]
            if artifact in seen_artifacts:
                continue
            seen_artifacts.add(artifact)
            deduped.append(step)

        if not deduped:
            return []

        # Repair ordering if the model mentioned actions out of order.
        ordering = ["parsed_query", "retrieval_result", "calculation_result", "report"]
        deduped.sort(key=lambda item: ordering.index(item["expected_artifact"]))
        for index, step in enumerate(deduped, start=1):
            step["step_id"] = f"step-{index}"

        if deduped[0]["expected_artifact"] != "parsed_query":
            return []
        if deduped[-1]["expected_artifact"] != "report":
            return []
        return deduped

    def _extract_artifact_sequence(self, raw: str) -> list[str]:
        candidates = ["parsed_query", "retrieval_result", "calculation_result", "report"]
        normalized = raw.replace("\n", ",").replace(" ", "")
        parts = [part.strip().lower() for part in normalized.split(",") if part.strip()]
        sequence = [part for part in parts if part in candidates]

        if not sequence:
            lowered = raw.lower()
            if "parse" in lowered or "parsed_query" in lowered:
                sequence.append("parsed_query")
            if any(token in lowered for token in ("retrieve", "retrieval", "evidence", "policy", "document")):
                sequence.append("retrieval_result")
            if any(token in lowered for token in ("calculate", "calculation", "compute", "arithmetic")):
                sequence.append("calculation_result")
            if any(token in lowered for token in ("report", "final", "answer", "summary")):
                sequence.append("report")

        deduped: list[str] = []
        for item in sequence:
            if item not in deduped:
                deduped.append(item)
        if not deduped:
            return []
        if deduped[0] != "parsed_query":
            deduped.insert(0, "parsed_query")
        if deduped[-1] != "report":
            deduped.append("report")
        return deduped

    def _validate_steps(self, raw_steps: object, fallback_plan: list[PlanStep]) -> list[PlanStep]:
        if not isinstance(raw_steps, list) or not raw_steps:
            raise ValueError("invalid llm plan")

        valid_skill_names = set(self.registry.names())
        normalized_steps: list[PlanStep] = []
        for index, raw_step in enumerate(raw_steps, start=1):
            if not isinstance(raw_step, dict):
                raise ValueError("plan step must be an object")

            goal = raw_step.get("goal")
            expected_artifact = raw_step.get("expected_artifact")
            candidate_skills = raw_step.get("candidate_skills", [])
            inputs_needed = raw_step.get("inputs_needed", [])
            if not isinstance(goal, str) or not goal.strip():
                raise ValueError("plan step missing goal")
            if not isinstance(expected_artifact, str) or not expected_artifact.strip():
                raise ValueError("plan step missing expected_artifact")
            if not isinstance(candidate_skills, list) or not candidate_skills:
                raise ValueError("plan step missing candidate_skills")
            if not isinstance(inputs_needed, list):
                raise ValueError("plan step missing inputs_needed")

            filtered_candidates = [name for name in candidate_skills if name in valid_skill_names]
            if not filtered_candidates:
                raise ValueError("plan step contains no known candidate skills")

            normalized_steps.append(
                PlanStep(
                    step_id=raw_step.get("step_id") or f"step-{index}",
                    goal=goal.strip(),
                    inputs_needed=[str(item) for item in inputs_needed],
                    candidate_skills=filtered_candidates,
                    expected_artifact=expected_artifact.strip(),
                    metadata={"planner_source": "llm"},
                )
            )

        if normalized_steps[0].expected_artifact != "parsed_query":
            raise ValueError("first llm step must produce parsed_query")
        if normalized_steps[-1].expected_artifact != "report":
            raise ValueError("last llm step must produce report")
        if len(normalized_steps) > len(fallback_plan) + 1:
            raise ValueError("llm plan too long for current mvp")

        return normalized_steps
