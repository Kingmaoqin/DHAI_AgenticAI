import os

from agent_core.core.finalizer import Finalizer
from agent_core.core.parser import TaskParser
from agent_core.core.planner import Planner
from agent_core.core.router import SkillRouter
from agent_core.core.state_machine import StateMachineRunner
from agent_core.core.verifier import EvidenceVerifier, SchemaVerifier
from agent_core.policies.builtin import CalculationPolicy, GeneralQAPolicy, MixedAnalysisPolicy
from agent_core.services.llm_client import OpenAICompatibleLLMClient
from agent_core.skills.builtin import (
    CalculatorSkill,
    LLMQueryParserSkill,
    LLMReportWriterSkill,
    ParserSkill,
    ReportWriterSkill,
    RetrievalSkill,
)
from agent_core.skills.registry import SkillRegistry


def build_default_runner() -> StateMachineRunner:
    llm_endpoint = os.getenv("LOCAL_LLM_ENDPOINT") or os.getenv("OPENAI_COMPAT_BASE_URL")
    llm_client = (
        OpenAICompatibleLLMClient(
            base_url=llm_endpoint,
            api_key=os.getenv("LLM_API_KEY"),
            model=os.getenv("LLM_MODEL"),
        )
        if llm_endpoint
        else None
    )

    registry = SkillRegistry()
    registry.register(ParserSkill())
    registry.register(LLMQueryParserSkill(llm_client=llm_client))
    registry.register(RetrievalSkill())
    registry.register(CalculatorSkill())
    registry.register(LLMReportWriterSkill(llm_client=llm_client))
    registry.register(ReportWriterSkill())

    policies = [
        MixedAnalysisPolicy(),
        GeneralQAPolicy(),
        CalculationPolicy(),
    ]

    return StateMachineRunner(
        task_parser=TaskParser(),
        planner=Planner(registry=registry, llm_client=llm_client),
        policies=policies,
        router=SkillRouter(registry, llm_client=llm_client),
        schema_verifier=SchemaVerifier(),
        evidence_verifier=EvidenceVerifier(),
        finalizer=Finalizer(),
    )
