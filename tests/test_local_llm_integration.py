import json
import os
import unittest
from unittest.mock import patch

from agent_core import build_default_runner


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def _fake_urlopen(request, timeout=10):  # noqa: ANN001
    url = request if isinstance(request, str) else request.full_url
    if url.endswith("/health"):
        return _FakeResponse({"status": "ok", "model_loaded": True})
    if url.endswith("/v1/chat/completions"):
        request_payload = json.loads(request.data.decode("utf-8"))
        system_prompt = request_payload["messages"][0]["content"]

        if "workflow planner" in system_prompt:
            return _FakeResponse(
                {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": (
                                    "Here is the valid plan:\n"
                                    + json.dumps(
                                        {
                                            "steps": [
                                                {
                                                    "step_id": "step-1",
                                                    "goal": "Use the LLM parser to structure the request.",
                                                    "inputs_needed": ["task_spec.raw_query"],
                                                    "candidate_skills": ["llm_query_parser", "parser"],
                                                    "expected_artifact": "parsed_query",
                                                },
                                                {
                                                    "step_id": "step-2",
                                                    "goal": "Retrieve supporting handbook evidence.",
                                                    "inputs_needed": ["artifact:parsed_query"],
                                                    "candidate_skills": ["retrieval"],
                                                    "expected_artifact": "retrieval_result",
                                                },
                                                {
                                                    "step_id": "step-3",
                                                    "goal": "Compute the arithmetic expression.",
                                                    "inputs_needed": ["artifact:parsed_query"],
                                                    "candidate_skills": ["calculator"],
                                                    "expected_artifact": "calculation_result",
                                                },
                                                {
                                                    "step_id": "step-4",
                                                    "goal": "Use the LLM report writer to finish the response.",
                                                    "inputs_needed": ["artifact:retrieval_result", "artifact:calculation_result"],
                                                    "candidate_skills": ["llm_report_writer", "report_writer"],
                                                    "expected_artifact": "report",
                                                },
                                            ]
                                        }
                                    )
                                ),
                            }
                        }
                    ]
                }
            )

        if "workflow router" in system_prompt:
            user_payload = json.loads(request_payload["messages"][1]["content"])
            expected_artifact = user_payload["current_step"]["expected_artifact"]
            selected_skill = "llm_query_parser" if expected_artifact == "parsed_query" else "llm_report_writer"
            return _FakeResponse(
                {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": f"I choose {selected_skill} because it should handle this step best.",
                            }
                        }
                    ]
                }
            )

        if "query parser" in system_prompt:
            user_payload = json.loads(request_payload["messages"][1]["content"])
            fallback_parse = user_payload["fallback_parse"]
            fallback_parse["retrieval_query"] = "office handbook lunch reimbursement"
            return _FakeResponse(
                {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": json.dumps(fallback_parse),
                            }
                        }
                    ]
                }
            )

        return _FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(
                                {
                                    "answer": 42,
                                    "summary": "policy=expense_policy | calc=42",
                                    "evidence_ids": [],
                                }
                            ),
                        }
                    }
                ]
            }
        )
    raise AssertionError(f"Unexpected URL: {url}")


class LocalLLMIntegrationTest(unittest.TestCase):
    def test_planner_and_router_use_local_llm_when_available(self) -> None:
        os.environ["LOCAL_LLM_ENDPOINT"] = "http://127.0.0.1:18080"
        try:
            with patch("urllib.request.urlopen", side_effect=_fake_urlopen):
                runner = build_default_runner()
                run_state = runner.run(
                    query=(
                        "Based on the office handbook, what is the lunch reimbursement limit, "
                        "and what is 18 + 24? Return a short report with evidence."
                    )
                )
        finally:
            os.environ.pop("LOCAL_LLM_ENDPOINT", None)

        self.assertEqual(run_state.current_state, "DONE")
        self.assertEqual(run_state.planning_mode, "llm")
        self.assertEqual(run_state.final_response.answer, "42")
        self.assertTrue(run_state.final_response.evidence_ids)
        self.assertEqual(run_state.plan[0].selected_skill, "llm_query_parser")
        self.assertEqual(run_state.plan[-1].selected_skill, "llm_report_writer")
        self.assertEqual(run_state.plan[0].metadata["routing_mode"], "llm")
        self.assertEqual(run_state.plan[-1].metadata["routing_mode"], "llm")


if __name__ == "__main__":
    unittest.main()
