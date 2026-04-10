from __future__ import annotations

from agent_core.schemas import Artifact, RunState, TaskSpec

import re


class SchemaVerifier:
    REQUIRED_FIELDS = ("answer", "summary", "evidence_ids")

    def verify(self, artifact: Artifact) -> tuple[bool, str]:
        missing = [field for field in self.REQUIRED_FIELDS if field not in artifact.content]
        if missing:
            return False, f"missing fields: {', '.join(missing)}"
        if not isinstance(artifact.content["answer"], str):
            return False, "answer must be a string"
        if not isinstance(artifact.content["summary"], str):
            return False, "summary must be a string"
        if not isinstance(artifact.content["evidence_ids"], list):
            return False, "evidence_ids must be a list"
        if not all(isinstance(item, str) for item in artifact.content["evidence_ids"]):
            return False, "every evidence_id must be a string"
        return True, "schema ok"


class EvidenceVerifier:
    def verify(self, task_spec: TaskSpec, artifact: Artifact, run_state: RunState) -> tuple[bool, str]:
        if not task_spec.constraints.get("require_evidence"):
            return True, "evidence not required"

        evidence_ids = artifact.content.get("evidence_ids", [])
        if not evidence_ids:
            return False, "evidence required but none provided"

        for artifact_id in evidence_ids:
            if artifact_id not in run_state.artifacts:
                return False, f"unknown evidence artifact: {artifact_id}"
        return True, "evidence ok"


class NumericVerifier:
    def verify(self, artifact: Artifact) -> tuple[bool, str]:
        answer = artifact.content.get("answer", "")
        if not isinstance(answer, str):
            return False, "answer is not a string"
        # check if answer contains any digit
        if not re.search(r"\d", answer):
            return False, "answer contains no numeric value"
        return True, "numeric check ok"