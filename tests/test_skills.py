from agent_core.skills.builtin import CalculatorSkill, RetrievalSkill
from agent_core.schemas import Artifact, PlanStep, RunState, TaskSpec
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