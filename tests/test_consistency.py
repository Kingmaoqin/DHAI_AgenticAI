from agent_core.skills.builtin import (
    CalculatorSkill,
    LLMQueryParserSkill,
    LLMReportWriterSkill,
    ParserSkill,
    ReportWriterSkill,
    RetrievalSkill,
    UnitNormalizerSkill,
)
from agent_core.skills import SkillRegistry
from agent_core import build_default_runner

# Check 1 — all skills can be imported
all_skills = [
    CalculatorSkill,
    LLMQueryParserSkill,
    LLMReportWriterSkill,
    ParserSkill,
    ReportWriterSkill,
    RetrievalSkill,
    UnitNormalizerSkill,
]
for skill_class in all_skills:
    instance = skill_class()
    assert isinstance(instance.name, str), f"{skill_class.__name__} missing name"
    assert isinstance(instance.description, str), f"{skill_class.__name__} missing description"
    assert len(instance.supported_artifacts) > 0, f"{skill_class.__name__} missing supported_artifacts"
print("Check 1 passed — all skills importable and have required attributes!")

# Check 2 — all skills are registered in bootstrap
runner = build_default_runner()
registered_names = runner.router.registry.names()

expected_skills = [
    "parser",
    "llm_query_parser",
    "retrieval",
    "calculator",
    "report_writer",
    "llm_report_writer",
]
for name in expected_skills:
    assert name in registered_names, f"Skill '{name}' not registered in bootstrap!"
print("Check 2 passed — all core skills registered in bootstrap!")

# Check 3 — no skill has an empty name or description
for skill_class in all_skills:
    instance = skill_class()
    assert instance.name.strip() != "", f"{skill_class.__name__} has empty name"
    assert instance.description.strip() != "", f"{skill_class.__name__} has empty description"
print("Check 3 passed — no skill has empty name or description!")

print("\nAll consistency checks passed!")