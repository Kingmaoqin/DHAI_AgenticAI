from __future__ import annotations

from agent_core.schemas import Artifact, FinalResponse, RunState


class Finalizer:
    def finalize(self, report_artifact: Artifact, run_state: RunState) -> FinalResponse:
        return FinalResponse(
            answer=report_artifact.content["answer"],
            summary=report_artifact.content["summary"],
            evidence_ids=report_artifact.content["evidence_ids"],
            artifacts=list(run_state.artifacts.keys()),
        )
