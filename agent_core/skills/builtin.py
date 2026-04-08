from __future__ import annotations

import ast
import json
import operator
import re
import uuid

from agent_core.services.llm_client import OpenAICompatibleLLMClient, coerce_report_content, extract_json_object
from agent_core.schemas import Artifact, PlanStep, RunState, TaskSpec
from agent_core.skills.base import Skill

MOCK_DOCUMENTS = {
    "treasury_bulletin_1944_01": {
        "title": "U.S. Treasury Bulletin, January 1944",
        "text": (
            "Table: Federal Government Expenditures by Agency. "
            "Fiscal Year 1934. "
            "Veterans Administration (includes public works): 507 million dollars. "
            "Note: excludes revolving funds and transfers to trust fund accounts."
        ),
    },
    "treasury_bulletin_1998_12": {
        "title": "U.S. Treasury Bulletin, December 1998",
        "text": (
            "Table: U.S. Claims on Foreigners. "
            "Calendar Year 1995. "
            "Highest claim on a single country: 103,375 million dollars. "
            "Note: excludes territories and regional aggregates."
        ),
    },
    "treasury_bulletin_1946_07": {
        "title": "U.S. Treasury Bulletin, July 1946",
        "text": (
            "Table: Series E Savings Bonds — Payroll Savings Plans by State. "
            "August 1945 data. "
            "Page 42."
        ),
    },
}

ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.USub: operator.neg,
}


def _latest_artifact(run_state: RunState, artifact_type: str) -> Artifact | None:
    for artifact in reversed(list(run_state.artifacts.values())):
        if artifact.type == artifact_type:
            return artifact
    return None


def _safe_eval(expression: str) -> float:
    def _eval(node: ast.AST) -> float:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.BinOp) and type(node.op) in ALLOWED_OPERATORS:
            return ALLOWED_OPERATORS[type(node.op)](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in ALLOWED_OPERATORS:
            return ALLOWED_OPERATORS[type(node.op)](_eval(node.operand))
        raise ValueError(f"Unsupported expression: {expression}")

    tree = ast.parse(expression, mode="eval")
    return _eval(tree)


def _rule_parse_content(query: str, task_spec: TaskSpec) -> dict[str, object]:
    math_match = re.search(r"(\d+\s*[\+\-\*/]\s*\d+)", query)
    retrieval_query = re.sub(r"\band what is\b.*", "", query, flags=re.IGNORECASE).strip(" ?.!")
    return {
        "original_query": query,
        "retrieval_query": retrieval_query,
        "calculation_expression": math_match.group(1) if math_match else None,
        "needs_retrieval": task_spec.family in {"general_qa", "mixed_analysis"},
        "needs_calculation": task_spec.family in {"calculation_only", "mixed_analysis"},
    }


def _rule_render_report(retrieval: Artifact | None, calc: Artifact | None) -> dict[str, object]:
    answer_parts = []
    evidence_ids = []

    if retrieval is not None:
        answer_parts.append(
            f"{retrieval.content['title']} states: {retrieval.content['snippet']}"
        )
        evidence_ids.append(retrieval.artifact_id)

    if calc is not None:
        answer_parts.append(
            f"The calculation result is {calc.content['expression']} = {calc.content['value']}."
        )

    if not answer_parts:
        answer_parts.append("No evidence or calculation result was available.")

    summary = " | ".join(
        part
        for part in [
            f"policy={retrieval.content['doc_id']}" if retrieval is not None else "",
            f"calc={calc.content['value']}" if calc is not None else "",
        ]
        if part
    )
    return {
        "answer": " ".join(answer_parts),
        "summary": summary or "report generated",
        "evidence_ids": evidence_ids,
    }


class ParserSkill(Skill):
    name = "parser"
    description = "Rule-based parser that extracts retrieval text and arithmetic expressions from the raw query."
    supported_artifacts = ("parsed_query",)

    def can_handle(self, step: PlanStep, task_spec: TaskSpec, run_state: RunState) -> bool:
        return step.expected_artifact == "parsed_query"

    def run(self, step: PlanStep, task_spec: TaskSpec, run_state: RunState) -> Artifact:
        content = _rule_parse_content(task_spec.raw_query, task_spec)
        return Artifact(
            artifact_id=f"artifact-{uuid.uuid4().hex[:8]}",
            type="parsed_query",
            producer=self.name,
            content=content,
            confidence=0.95,
        )


class LLMQueryParserSkill(Skill):
    name = "llm_query_parser"
    description = "Local-LLM parser that converts the raw query into structured task slots."
    supported_artifacts = ("parsed_query",)

    def __init__(self, llm_client: OpenAICompatibleLLMClient | None = None) -> None:
        self.llm_client = llm_client

    def can_handle(self, step: PlanStep, task_spec: TaskSpec, run_state: RunState) -> bool:
        return (
            step.expected_artifact == "parsed_query"
            and self.llm_client is not None
            and self.llm_client.is_healthy()
        )

    def run(self, step: PlanStep, task_spec: TaskSpec, run_state: RunState) -> Artifact:
        content = _rule_parse_content(task_spec.raw_query, task_spec)
        prompt_payload = {
            "query": task_spec.raw_query,
            "family": task_spec.family,
            "required_fields": list(content.keys()),
            "fallback_parse": content,
        }
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a query parser in an agentic workflow. "
                    "Return strict JSON with keys original_query, retrieval_query, "
                    "calculation_expression, needs_retrieval, needs_calculation. "
                    "Do not add markdown fences."
                ),
            },
            {"role": "user", "content": json.dumps(prompt_payload, ensure_ascii=True)},
        ]

        try:
            raw = self.llm_client.chat_completion(messages=messages, max_tokens=220, temperature=0.1)
            parsed = extract_json_object(raw)
            if not isinstance(parsed.get("retrieval_query"), str):
                parsed["retrieval_query"] = content["retrieval_query"]
            if "original_query" not in parsed:
                parsed["original_query"] = task_spec.raw_query
            if "calculation_expression" not in parsed:
                parsed["calculation_expression"] = content["calculation_expression"]
            parsed["needs_retrieval"] = bool(parsed.get("needs_retrieval", content["needs_retrieval"]))
            parsed["needs_calculation"] = bool(parsed.get("needs_calculation", content["needs_calculation"]))
            content = parsed
            confidence = 0.8
            provenance = {"mode": "llm"}
        except Exception:
            confidence = 0.6
            provenance = {"mode": "llm_with_rule_fallback"}

        return Artifact(
            artifact_id=f"artifact-{uuid.uuid4().hex[:8]}",
            type="parsed_query",
            producer=self.name,
            content=content,
            confidence=confidence,
            provenance=provenance,
        )


class RetrievalSkill(Skill):
    name = "retrieval"
    description = "Keyword retrieval over the built-in mock handbook documents."
    supported_artifacts = ("retrieval_result",)

    def can_handle(self, step: PlanStep, task_spec: TaskSpec, run_state: RunState) -> bool:
        return step.expected_artifact == "retrieval_result"

    def run(self, step: PlanStep, task_spec: TaskSpec, run_state: RunState) -> Artifact:
        parsed = _latest_artifact(run_state, "parsed_query")
        if parsed is None:
            raise ValueError("retrieval requires parsed_query artifact")

        query_terms = set(re.findall(r"[a-zA-Z]+", parsed.content["retrieval_query"].lower()))
        best_doc = None
        best_score = -1
        for doc_id, payload in MOCK_DOCUMENTS.items():
            doc_terms = set(re.findall(r"[a-zA-Z]+", payload["text"].lower())) | set(
                re.findall(r"[a-zA-Z]+", payload["title"].lower())
            )
            score = len(query_terms & doc_terms)
            if score > best_score:
                best_score = score
                best_doc = (doc_id, payload)

        if best_doc is None:
            raise ValueError("no retrieval candidate found")

        doc_id, payload = best_doc
        return Artifact(
            artifact_id=f"artifact-{uuid.uuid4().hex[:8]}",
            type="retrieval_result",
            producer=self.name,
            content={
                "doc_id": doc_id,
                "title": payload["title"],
                "snippet": payload["text"],
            },
            confidence=0.8,
            provenance={"source": "mock_documents", "doc_id": doc_id},
        )


class CalculatorSkill(Skill):
    name = "calculator"
    description = "Deterministic arithmetic evaluator for simple expressions."
    supported_artifacts = ("calculation_result",)

    def can_handle(self, step: PlanStep, task_spec: TaskSpec, run_state: RunState) -> bool:
        return step.expected_artifact == "calculation_result"

    def run(self, step: PlanStep, task_spec: TaskSpec, run_state: RunState) -> Artifact:
        parsed = _latest_artifact(run_state, "parsed_query")
        if parsed is None:
            raise ValueError("calculator requires parsed_query artifact")

        expression = parsed.content.get("calculation_expression")
        if not expression:
            raise ValueError("no calculation expression found")

        value = _safe_eval(expression)
        rendered = int(value) if value.is_integer() else round(value, 4)
        return Artifact(
            artifact_id=f"artifact-{uuid.uuid4().hex[:8]}",
            type="calculation_result",
            producer=self.name,
            content={
                "expression": expression,
                "value": rendered,
            },
            confidence=1.0,
        )


class ReportWriterSkill(Skill):
    name = "report_writer"
    description = "Template-based deterministic report writer."
    supported_artifacts = ("report",)

    def can_handle(self, step: PlanStep, task_spec: TaskSpec, run_state: RunState) -> bool:
        return step.expected_artifact == "report"

    def run(self, step: PlanStep, task_spec: TaskSpec, run_state: RunState) -> Artifact:
        retrieval = _latest_artifact(run_state, "retrieval_result")
        calc = _latest_artifact(run_state, "calculation_result")
        content = _rule_render_report(retrieval, calc)

        return Artifact(
            artifact_id=f"artifact-{uuid.uuid4().hex[:8]}",
            type="report",
            producer=self.name,
            content=content,
            confidence=0.9,
        )
    
class UnitNormalizerSkill(Skill):
    name = "unit_normalizer"
    description = "Converts financial text values like '$1.2 billion' to plain floats."
    supported_artifacts = ("normalized_value",)

    def can_handle(self, step: PlanStep, task_spec: TaskSpec, run_state: RunState) -> bool:
        return step.expected_artifact == "normalized_value"

    def run(self, step: PlanStep, task_spec: TaskSpec, run_state: RunState) -> Artifact:
        parsed = _latest_artifact(run_state, "parsed_query")
        raw_text = parsed.content.get("retrieval_query", "") if parsed else ""
        value = self._normalize(raw_text)
        return Artifact(
            artifact_id=f"artifact-{uuid.uuid4().hex[:8]}",
            type="normalized_value",
            producer=self.name,
            content={"raw": raw_text, "value": value},
            confidence=1.0,
        )

    def _normalize(self, text: str) -> float:
        text = text.strip().lower().replace(",", "").replace("$", "")
        if "%" in text:
            return float(re.sub(r"[^\d.]", "", text)) / 100
        if "trillion" in text or text.endswith("t"):
            return float(re.sub(r"[^\d.]", "", text)) * 1_000_000_000_000
        if "billion" in text or text.endswith("b"):
            return float(re.sub(r"[^\d.]", "", text)) * 1_000_000_000
        if "million" in text or text.endswith("m"):
            return float(re.sub(r"[^\d.]", "", text)) * 1_000_000
        return float(re.sub(r"[^\d.]", "", text))
    
class LLMReportWriterSkill(Skill):
    name = "llm_report_writer"
    description = "Local-LLM report writer that converts retrieved evidence and calculations into final JSON."
    supported_artifacts = ("report",)

    def __init__(self, llm_client: OpenAICompatibleLLMClient | None = None) -> None:
        self.llm_client = llm_client

    def can_handle(self, step: PlanStep, task_spec: TaskSpec, run_state: RunState) -> bool:
        return (
            step.expected_artifact == "report"
            and self.llm_client is not None
            and self.llm_client.is_healthy()
        )

    def run(self, step: PlanStep, task_spec: TaskSpec, run_state: RunState) -> Artifact:
        retrieval = _latest_artifact(run_state, "retrieval_result")
        calc = _latest_artifact(run_state, "calculation_result")
        content = self._run_with_llm(task_spec=task_spec, retrieval=retrieval, calc=calc)
        if content is None:
            content = _rule_render_report(retrieval, calc)
            confidence = 0.6
            provenance = {"mode": "llm_failed_rule_fallback"}
        else:
            content = coerce_report_content(content, [retrieval.artifact_id] if retrieval is not None else [])
            confidence = 0.75
            provenance = {"endpoint": self.llm_client.base_url}

        return Artifact(
            artifact_id=f"artifact-{uuid.uuid4().hex[:8]}",
            type="report",
            producer=self.name,
            content=content,
            confidence=confidence,
            provenance=provenance,
        )

    def _run_with_llm(
        self,
        task_spec: TaskSpec,
        retrieval: Artifact | None,
        calc: Artifact | None,
    ) -> dict[str, object] | None:
        evidence_ids = [retrieval.artifact_id] if retrieval is not None else []
        prompt_payload = {
            "query": task_spec.raw_query,
            "retrieval": retrieval.content if retrieval is not None else None,
            "calculation": calc.content if calc is not None else None,
            "required_fields": ["answer", "summary", "evidence_ids"],
            "evidence_ids": evidence_ids,
        }
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a report writer in an agentic workflow. "
                    "Return strict JSON with keys answer, summary, evidence_ids. "
                    "Do not add markdown fences."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(prompt_payload, ensure_ascii=True),
            },
        ]

        try:
            raw = self.llm_client.chat_completion(messages=messages)
            content = extract_json_object(raw)
            if not isinstance(content.get("evidence_ids"), list):
                return None
            if not content["evidence_ids"] and evidence_ids:
                content["evidence_ids"] = evidence_ids
            return content
        except Exception:
            return None
