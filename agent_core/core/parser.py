from __future__ import annotations

import re
import uuid

from agent_core.schemas import TaskSpec


class TaskParser:
    def parse(self, query: str) -> TaskSpec:
        lowered = query.lower()
        has_math = bool(re.search(r"\d+\s*[\+\-\*/]\s*\d+", query))
        asks_for_source = any(token in lowered for token in ("based on", "handbook", "policy", "evidence"))

        if has_math and asks_for_source:
            family = "mixed_analysis"
        elif has_math:
            family = "calculation_only"
        else:
            family = "general_qa"

        domain = "operations" if any(token in lowered for token in ("handbook", "policy", "reimbursement")) else "general"
        constraints = {
            "require_evidence": asks_for_source or family != "calculation_only",
            "format": "json",
            "max_steps": 4,
        }

        return TaskSpec(
            task_id=f"task-{uuid.uuid4().hex[:8]}",
            raw_query=query,
            domain=domain,
            family=family,
            modalities=["text"],
            constraints=constraints,
            output_schema={
                "answer": "string",
                "summary": "string",
                "evidence_ids": "list[str]",
            },
            eval_focus=["traceability", "schema_validity", "evidence_grounding"],
            budget={"max_steps": 4, "latency_hint": "low"},
        )
