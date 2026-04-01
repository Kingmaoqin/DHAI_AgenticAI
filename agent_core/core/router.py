from __future__ import annotations

import json
from dataclasses import dataclass

from agent_core.schemas import PlanStep, RunState, TaskSpec
from agent_core.services.llm_client import OpenAICompatibleLLMClient, extract_json_object, extract_skill_name
from agent_core.skills.base import Skill
from agent_core.skills.registry import SkillRegistry


@dataclass
class RouteDecision:
    skill: Skill
    mode: str
    reason: str


class SkillRouter:
    def __init__(self, registry: SkillRegistry, llm_client: OpenAICompatibleLLMClient | None = None) -> None:
        self.registry = registry
        self.llm_client = llm_client

    def select(self, step: PlanStep, task_spec: TaskSpec, run_state: RunState) -> RouteDecision:
        compatible_skills: list[Skill] = []
        for skill_name in step.candidate_skills:
            skill = self.registry.get(skill_name)
            if skill.can_handle(step=step, task_spec=task_spec, run_state=run_state):
                compatible_skills.append(skill)

        if not compatible_skills:
            raise ValueError(f"No skill available for step {step.step_id}: {step.goal}")

        if self.llm_client is not None and self.llm_client.is_healthy() and len(compatible_skills) > 1:
            decision = self._select_with_llm(
                step=step,
                task_spec=task_spec,
                run_state=run_state,
                compatible_skills=compatible_skills,
            )
            if decision is not None:
                preferred = self._prefer_llm_skill(step=step, compatible_skills=compatible_skills)
                if preferred is not None and not decision.skill.name.startswith("llm_"):
                    return preferred
                return decision

            preferred = self._prefer_llm_skill(step=step, compatible_skills=compatible_skills)
            if preferred is not None:
                return preferred

        return RouteDecision(
            skill=compatible_skills[0],
            mode="rule",
            reason="Selected the first compatible skill using deterministic fallback.",
        )

    def _select_with_llm(
        self,
        step: PlanStep,
        task_spec: TaskSpec,
        run_state: RunState,
        compatible_skills: list[Skill],
    ) -> RouteDecision | None:
        direct_decision = self._select_with_simple_prompt(step=step, compatible_skills=compatible_skills)
        if direct_decision is not None:
            return direct_decision

        payload = {
            "query": task_spec.raw_query,
            "family": task_spec.family,
            "current_step": {
                "step_id": step.step_id,
                "goal": step.goal,
                "expected_artifact": step.expected_artifact,
                "inputs_needed": step.inputs_needed,
            },
            "available_artifacts": [
                {
                    "artifact_id": artifact.artifact_id,
                    "type": artifact.type,
                    "producer": artifact.producer,
                }
                for artifact in run_state.artifacts.values()
            ],
            "candidate_skills": [skill.metadata() for skill in compatible_skills],
        }
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a workflow router for an agentic system. "
                    "Return strict JSON with keys selected_skill and reason. "
                    "Pick exactly one name from candidate_skills. "
                    "selected_skill must exactly match one candidate name. Do not add markdown fences."
                ),
            },
            {"role": "user", "content": json.dumps(payload, ensure_ascii=True)},
        ]

        try:
            raw = self.llm_client.chat_completion(messages=messages, max_tokens=180, temperature=0.1)
        except Exception:
            return None

        response = None
        try:
            response = extract_json_object(raw)
        except Exception:
            response = None

        skill_name = None
        reason = "LLM selected this skill."
        if response is not None:
            skill_name = (
                response.get("selected_skill")
                or response.get("skill")
                or response.get("tool")
                or response.get("choice")
                or response.get("name")
            )
            reason = str(response.get("reason", reason))

        if not isinstance(skill_name, str):
            allowed_names = [skill.name for skill in compatible_skills]
            skill_name = extract_skill_name(raw, allowed_names)
            if skill_name is None:
                return None
            reason = f"Recovered skill selection from non-JSON model output: {raw[:120]!r}"

        for skill in compatible_skills:
            if skill.name == skill_name:
                return RouteDecision(skill=skill, mode="llm", reason=str(reason))
        return None

    def _select_with_simple_prompt(
        self,
        step: PlanStep,
        compatible_skills: list[Skill],
    ) -> RouteDecision | None:
        allowed_names = [skill.name for skill in compatible_skills]
        messages = [
            {
                "role": "system",
                "content": (
                    "Choose exactly one skill name for this step. "
                    f"Valid skill names: {', '.join(allowed_names)}. "
                    "Reply with only the exact skill name and nothing else."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Step goal: {step.goal}\n"
                    f"Expected artifact: {step.expected_artifact}\n"
                    f"Candidate skills: {', '.join(allowed_names)}"
                ),
            },
        ]
        try:
            raw = self.llm_client.chat_completion(messages=messages, max_tokens=20, temperature=0.0)
        except Exception:
            return None

        skill_name = extract_skill_name(raw, allowed_names)
        if skill_name is None:
            return None
        for skill in compatible_skills:
            if skill.name == skill_name:
                return RouteDecision(
                    skill=skill,
                    mode="llm",
                    reason=f"Direct skill selection prompt chose {skill_name}.",
                )
        return None

    def _prefer_llm_skill(
        self,
        step: PlanStep,
        compatible_skills: list[Skill],
    ) -> RouteDecision | None:
        for skill in compatible_skills:
            if skill.name.startswith("llm_"):
                return RouteDecision(
                    skill=skill,
                    mode="llm",
                    reason=f"Preferred LLM-native skill {skill.name} for artifact {step.expected_artifact}.",
                )
        return None
