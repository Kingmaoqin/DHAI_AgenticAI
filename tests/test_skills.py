from agent_core.skills.builtin import CalculatorSkill, RetrievalSkill
from agent_core.schemas import Artifact, PlanStep, RunState, TaskSpec
from agent_core.skills.extractors import extract_number, extract_date, extract_table_value

import uuid

def make_step(expected_artifact):
    return PlanStep(
        step_id="step-1",
        goal="test step",
        inputs_needed=[],
        candidate_skills=[],
        expected_artifact=expected_artifact,
    )

def make_run_state():
    return RunState(run_id=f"run-{uuid.uuid4().hex[:8]}")

# Test CalculatorSkill
calc_skill = CalculatorSkill()
run_state = make_run_state()
run_state.add_artifact(Artifact(
    artifact_id="artifact-test-001",
    type="parsed_query",
    producer="parser",
    content={
        "original_query": "what is 18 + 24?",
        "retrieval_query": "what is 18 + 24?",
        "calculation_expression": "18 + 24",
        "needs_retrieval": False,
        "needs_calculation": True,
    },
    confidence=0.95,
))
step = make_step("calculation_result")
result = calc_skill.run(step, None, run_state)
assert result.content["value"] == 42
print("CalculatorSkill tests passed!")

# Test RetrievalSkill
retrieval_skill = RetrievalSkill()
run_state2 = make_run_state()
run_state2.add_artifact(Artifact(
    artifact_id="artifact-test-002",
    type="parsed_query",
    producer="parser",
    content={
        "original_query": "Veterans Administration expenditure 1934",
        "retrieval_query": "Veterans Administration expenditure 1934",
        "calculation_expression": None,
        "needs_retrieval": True,
        "needs_calculation": False,
    },
    confidence=0.95,
))
step2 = make_step("retrieval_result")
result2 = retrieval_skill.run(step2, None, run_state2)
assert result2.type == "retrieval_result"
assert "treasury" in result2.content["doc_id"]
print("RetrievalSkill tests passed!")

# Test extract_number
assert extract_number("Veterans Administration: 507 million dollars") == 507_000_000.0
assert extract_number("Highest claim: 103,375 million dollars") == 103_375_000_000.0
assert extract_number("Page 42") == 42.0
assert extract_number("3.5 percent") == 0.035
assert extract_number("1.2 billion") == 1_200_000_000.0
print("extract_number tests passed!")

# Test extract_date
assert extract_date("January 1985")       == (1985, 1)
assert extract_date("December 1998")      == (1998, 12)
assert extract_date("Fiscal Year 1934")   == (1934, None)
assert extract_date("Calendar Year 1995") == (1995, None)
print("extract_date tests passed!")

# Test extract_table_value
assert extract_table_value(
    "Veterans Administration (includes public works): 507",
    "Veterans Administration") == 507.0
assert extract_table_value(
    "Highest claim on a single country: 103375",
    "Highest claim") == 103375.0
print("extract_table_value tests passed!")