from __future__ import annotations

from agent_core.skills.base import Skill


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        self._skills[skill.name] = skill

    def get(self, skill_name: str) -> Skill:
        if skill_name not in self._skills:
            raise KeyError(f"Skill not found: {skill_name}")
        return self._skills[skill_name]

    def list(self) -> list[Skill]:
        return list(self._skills.values())

    def names(self) -> list[str]:
        return list(self._skills.keys())

    def metadata(self) -> list[dict[str, object]]:
        return [skill.metadata() for skill in self._skills.values()]
