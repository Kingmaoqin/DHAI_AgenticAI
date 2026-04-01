from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from agent_core.core.finalizer import Finalizer
from agent_core.core.parser import TaskParser
from agent_core.core.planner import Planner
from agent_core.core.router import SkillRouter
from agent_core.core.verifier import EvidenceVerifier, SchemaVerifier
from agent_core.policies.base import TaskPolicy
from agent_core.schemas import Artifact, RunState, TraceEvent


class StateMachineRunner:
    def __init__(
        self,
        task_parser: TaskParser,
        planner: Planner,
        policies: list[TaskPolicy],
        router: SkillRouter,
        schema_verifier: SchemaVerifier,
        evidence_verifier: EvidenceVerifier,
        finalizer: Finalizer,
    ) -> None:
        self.task_parser = task_parser
        self.planner = planner
        self.policies = policies
        self.router = router
        self.schema_verifier = schema_verifier
        self.evidence_verifier = evidence_verifier
        self.finalizer = finalizer

    def run(self, query: str, output_dir: str | Path | None = None) -> RunState:
        run_state = RunState(run_id=f"run-{uuid.uuid4().hex[:8]}")
        try:
            self._transition(run_state, "PARSE_TASK", "parse_query", [], [])
            task_spec = self.task_parser.parse(query)
            run_state.task_spec = task_spec

            self._transition(run_state, "CLASSIFY_TASK", "classify_family", [], [])
            policy = self._select_policy(task_spec.family)
            run_state.selected_policy = policy.name

            plan, planning_mode = self.planner.build_plan(task_spec, policy)
            run_state.planning_mode = planning_mode
            self._transition(
                run_state,
                "BUILD_PLAN",
                "build_plan",
                [],
                [step.step_id for step in plan],
                note=f"mode={planning_mode}",
            )
            run_state.plan = plan

            for step in run_state.plan:
                started = time.perf_counter()
                run_state.current_state = "EXECUTE_STEP"
                decision = self.router.select(step, task_spec, run_state)
                step.selected_skill = decision.skill.name
                artifact = decision.skill.run(step=step, task_spec=task_spec, run_state=run_state)
                step.status = "completed"
                step.metadata["routing_mode"] = decision.mode
                step.metadata["routing_reason"] = decision.reason
                run_state.add_artifact(artifact)
                self._append_trace(
                    run_state=run_state,
                    state="EXECUTE_STEP",
                    action=f"{step.step_id}:{decision.skill.name}",
                    input_ref=step.inputs_needed,
                    output_ref=[artifact.artifact_id],
                    latency_ms=int((time.perf_counter() - started) * 1000),
                    success=True,
                    note=f"{step.goal} | routing={decision.mode} | {decision.reason}",
                )

            report_artifact = self._find_report_artifact(run_state)

            self._transition(run_state, "FINAL_VERIFY", "verify_report", [], [report_artifact.artifact_id])
            schema_ok, schema_note = self.schema_verifier.verify(report_artifact)
            evidence_ok, evidence_note = self.evidence_verifier.verify(task_spec, report_artifact, run_state)
            if not schema_ok or not evidence_ok:
                raise ValueError(f"verification failed: {schema_note}; {evidence_note}")

            self._transition(run_state, "FORMAT_OUTPUT", "finalize_response", [report_artifact.artifact_id], [])
            run_state.final_response = self.finalizer.finalize(report_artifact, run_state)
            self._transition(run_state, "DONE", "run_complete", [], [])
        except Exception as exc:  # pragma: no cover - failure path is simple and traceable
            run_state.current_state = "FAIL"
            run_state.failures.append(str(exc))
            self._append_trace(
                run_state=run_state,
                state="FAIL",
                action="abort",
                input_ref=[],
                output_ref=[],
                latency_ms=0,
                success=False,
                note=str(exc),
            )
            raise
        finally:
            if output_dir is not None:
                self._persist_run(run_state, output_dir)

        return run_state

    def _select_policy(self, family: str) -> TaskPolicy:
        for policy in self.policies:
            if policy.supports(family):
                return policy
        raise ValueError(f"No policy registered for family={family}")

    def _find_report_artifact(self, run_state: RunState) -> Artifact:
        for artifact in reversed(list(run_state.artifacts.values())):
            if artifact.type == "report":
                return artifact
        raise ValueError("No report artifact produced")

    def _transition(
        self,
        run_state: RunState,
        new_state: str,
        action: str,
        input_ref: list[str],
        output_ref: list[str],
        note: str | None = None,
    ) -> None:
        run_state.current_state = new_state
        self._append_trace(
            run_state=run_state,
            state=new_state,
            action=action,
            input_ref=input_ref,
            output_ref=output_ref,
            latency_ms=0,
            success=True,
            note=note,
        )

    def _append_trace(
        self,
        run_state: RunState,
        state: str,
        action: str,
        input_ref: list[str],
        output_ref: list[str],
        latency_ms: int,
        success: bool,
        note: str | None = None,
    ) -> None:
        run_state.trace.append(
            TraceEvent(
                time=datetime.now(timezone.utc).isoformat(),
                state=state,
                action=action,
                input_ref=input_ref,
                output_ref=output_ref,
                latency_ms=latency_ms,
                success=success,
                note=note,
            )
        )

    def _persist_run(self, run_state: RunState, output_dir: str | Path) -> None:
        path = Path(output_dir)
        path.mkdir(parents=True, exist_ok=True)

        run_payload = run_state.to_dict()
        (path / f"{run_state.run_id}_state.json").write_text(
            json.dumps(run_payload, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )
        (path / f"{run_state.run_id}_trace.json").write_text(
            json.dumps([asdict(event) for event in run_state.trace], indent=2, ensure_ascii=True),
            encoding="utf-8",
        )
