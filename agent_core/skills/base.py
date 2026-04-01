from __future__ import annotations

from abc import ABC, abstractmethod

from agent_core.schemas import Artifact, PlanStep, RunState, TaskSpec


class Skill(ABC):
    name: str
    description: str = ""
    supported_artifacts: tuple[str, ...] = ()

    @abstractmethod
    def can_handle(self, step: PlanStep, task_spec: TaskSpec, run_state: RunState) -> bool:
        raise NotImplementedError

    @abstractmethod
    def run(self, step: PlanStep, task_spec: TaskSpec, run_state: RunState) -> Artifact:
        raise NotImplementedError

    def metadata(self) -> dict[str, object]:
        return {
            "name": self.name,
            "description": self.description,
            "supported_artifacts": list(self.supported_artifacts),
        }
