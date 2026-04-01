from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class TaskSpec:
    task_id: str
    raw_query: str
    domain: str
    family: str
    modalities: list[str]
    constraints: dict[str, Any]
    output_schema: dict[str, str]
    eval_focus: list[str]
    budget: dict[str, Any]


@dataclass
class PlanStep:
    step_id: str
    goal: str
    inputs_needed: list[str]
    candidate_skills: list[str]
    expected_artifact: str
    verifier: str | None = None
    selected_skill: str | None = None
    status: str = "pending"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Artifact:
    artifact_id: str
    type: str
    producer: str
    content: dict[str, Any]
    confidence: float | None = None
    provenance: dict[str, Any] = field(default_factory=dict)


@dataclass
class TraceEvent:
    time: str
    state: str
    action: str
    input_ref: list[str]
    output_ref: list[str]
    latency_ms: int
    success: bool
    note: str | None = None
    cost: float | None = None


@dataclass
class FinalResponse:
    answer: str
    summary: str
    evidence_ids: list[str]
    artifacts: list[str]


@dataclass
class RunState:
    run_id: str
    current_state: str = "INIT"
    selected_policy: str | None = None
    planning_mode: str = "rule"
    task_spec: TaskSpec | None = None
    plan: list[PlanStep] = field(default_factory=list)
    artifacts: dict[str, Artifact] = field(default_factory=dict)
    trace: list[TraceEvent] = field(default_factory=list)
    final_response: FinalResponse | None = None
    failures: list[str] = field(default_factory=list)

    def add_artifact(self, artifact: Artifact) -> None:
        self.artifacts[artifact.artifact_id] = artifact

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
