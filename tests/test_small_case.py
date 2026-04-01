import unittest

from agent_core import build_default_runner


class SmallCaseTest(unittest.TestCase):
    def test_mixed_analysis_case_runs(self) -> None:
        runner = build_default_runner()
        run_state = runner.run(
            query=(
                "Based on the office handbook, what is the lunch reimbursement limit, "
                "and what is 18 + 24? Return a short report with evidence."
            )
        )

        self.assertEqual(run_state.current_state, "DONE")
        self.assertEqual(run_state.selected_policy, "mixed_analysis")
        self.assertIn("50 USD", run_state.final_response.answer)
        self.assertIn("18 + 24 = 42", run_state.final_response.answer)
        self.assertTrue(run_state.final_response.evidence_ids)


if __name__ == "__main__":
    unittest.main()
