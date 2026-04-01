from __future__ import annotations

from abc import ABC, abstractmethod

from agent_core.schemas import PlanStep, TaskSpec


class TaskPolicy(ABC):
    name: str

    @abstractmethod
    def supports(self, family: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def build_plan(self, task_spec: TaskSpec) -> list[PlanStep]:
        raise NotImplementedError
