from __future__ import annotations

from agent_core.policies.base import TaskPolicy
from agent_core.schemas import PlanStep, TaskSpec


class CalculationPolicy(TaskPolicy):
    name = "calculation_only"

    def supports(self, family: str) -> bool:
        return family == self.name

    def build_plan(self, task_spec: TaskSpec) -> list[PlanStep]:
        return [
            PlanStep(
                step_id="step-1",
                goal="Parse the user query into structured slots.",
                inputs_needed=["task_spec.raw_query"],
                candidate_skills=["llm_query_parser", "parser"],
                expected_artifact="parsed_query",
            ),
            PlanStep(
                step_id="step-2",
                goal="Compute the arithmetic expression.",
                inputs_needed=["artifact:parsed_query"],
                candidate_skills=["calculator"],
                expected_artifact="calculation_result",
            ),
            PlanStep(
                step_id="step-3",
                goal="Write a final structured response.",
                inputs_needed=["artifact:calculation_result"],
                candidate_skills=["llm_report_writer", "report_writer"],
                expected_artifact="report",
            ),
        ]


class GeneralQAPolicy(TaskPolicy):
    name = "general_qa"

    def supports(self, family: str) -> bool:
        return family == self.name

    def build_plan(self, task_spec: TaskSpec) -> list[PlanStep]:
        return [
            PlanStep(
                step_id="step-1",
                goal="Parse the user query into structured slots.",
                inputs_needed=["task_spec.raw_query"],
                candidate_skills=["llm_query_parser", "parser"],
                expected_artifact="parsed_query",
            ),
            PlanStep(
                step_id="step-2",
                goal="Retrieve relevant evidence from the mock knowledge base.",
                inputs_needed=["artifact:parsed_query"],
                candidate_skills=["retrieval"],
                expected_artifact="retrieval_result",
            ),
            PlanStep(
                step_id="step-3",
                goal="Write a final structured response.",
                inputs_needed=["artifact:retrieval_result"],
                candidate_skills=["llm_report_writer", "report_writer"],
                expected_artifact="report",
            ),
        ]


class MixedAnalysisPolicy(TaskPolicy):
    name = "mixed_analysis"

    def supports(self, family: str) -> bool:
        return family == self.name

    def build_plan(self, task_spec: TaskSpec) -> list[PlanStep]:
        return [
            PlanStep(
                step_id="step-1",
                goal="Parse the user query into structured slots.",
                inputs_needed=["task_spec.raw_query"],
                candidate_skills=["llm_query_parser", "parser"],
                expected_artifact="parsed_query",
            ),
            PlanStep(
                step_id="step-2",
                goal="Retrieve the relevant policy evidence.",
                inputs_needed=["artifact:parsed_query"],
                candidate_skills=["retrieval"],
                expected_artifact="retrieval_result",
            ),
            PlanStep(
                step_id="step-3",
                goal="Compute the requested arithmetic expression.",
                inputs_needed=["artifact:parsed_query"],
                candidate_skills=["calculator"],
                expected_artifact="calculation_result",
            ),
            PlanStep(
                step_id="step-4",
                goal="Write a final structured response.",
                inputs_needed=["artifact:retrieval_result", "artifact:calculation_result"],
                candidate_skills=["llm_report_writer", "report_writer"],
                expected_artifact="report",
            ),
        ]
