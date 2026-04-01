from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any


class OpenAICompatibleLLMClient:
    def __init__(
        self,
        base_url: str,
        timeout_seconds: int = 10,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.api_key = api_key or os.getenv("LLM_API_KEY")
        self.model = model or os.getenv("LLM_MODEL")

    def is_healthy(self) -> bool:
        try:
            with urllib.request.urlopen(
                f"{self.base_url}/health",
                timeout=self.timeout_seconds,
            ) as response:
                payload = json.loads(response.read().decode("utf-8"))
            return payload.get("status") == "ok"
        except urllib.error.HTTPError as exc:
            # Many public OpenAI-compatible APIs do not expose /health.
            if exc.code in {404, 405}:
                return True
            return False
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            return False

    def chat_completion(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 220,
        temperature: float = 0.2,
    ) -> str:
        body = json.dumps(
            {
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                **({"model": self.model} if self.model else {}),
            }
        ).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = urllib.request.Request(
            f"{self.base_url}/v1/chat/completions",
            data=body,
            headers=headers,
            method="POST",
        )

        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            payload: dict[str, Any] = json.loads(response.read().decode("utf-8"))

        return payload["choices"][0]["message"]["content"]

    def chat_json(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 220,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        raw = self.chat_completion(
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return extract_json_object(raw)


def extract_json_object(raw: str) -> dict[str, Any]:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        for candidate in _extract_balanced_json_objects(cleaned):
            try:
                payload = json.loads(candidate)
                break
            except json.JSONDecodeError:
                continue
        else:
            raise

    if not isinstance(payload, dict):
        raise ValueError("Expected a JSON object")
    return payload


def _extract_balanced_json_objects(text: str) -> list[str]:
    results: list[str] = []
    stack = 0
    start = None
    for index, char in enumerate(text):
        if char == "{":
            if stack == 0:
                start = index
            stack += 1
        elif char == "}":
            if stack == 0:
                continue
            stack -= 1
            if stack == 0 and start is not None:
                results.append(text[start : index + 1])
                start = None
    return results


def extract_skill_name(raw: str, allowed_names: list[str]) -> str | None:
    cleaned = raw.strip()
    for name in allowed_names:
        if re.search(rf"\b{re.escape(name)}\b", cleaned):
            return name

    normalized_cleaned = _normalize_text(cleaned)
    alias_map = {
        "llm_query_parser": ["llm query parser", "llm parser", "query parser", "local llm parser"],
        "parser": ["rule parser", "rule-based parser", "parser"],
        "llm_report_writer": ["llm report writer", "report writer", "llm writer"],
        "report_writer": ["template report writer", "rule report writer", "report writer"],
        "retrieval": ["retrieval", "retrieve evidence", "search handbook"],
        "calculator": ["calculator", "calculate", "arithmetic"],
    }
    for name in allowed_names:
        aliases = alias_map.get(name, [name.replace("_", " ")])
        for alias in aliases:
            if _normalize_text(alias) in normalized_cleaned:
                return name
    return None


def coerce_report_content(content: dict[str, Any], fallback_evidence_ids: list[str]) -> dict[str, Any]:
    normalized = dict(content)
    normalized["answer"] = str(normalized.get("answer", ""))
    normalized["summary"] = str(normalized.get("summary", ""))

    evidence_ids = normalized.get("evidence_ids", fallback_evidence_ids)
    if isinstance(evidence_ids, list):
        normalized["evidence_ids"] = [str(item) for item in evidence_ids]
    else:
        normalized["evidence_ids"] = [str(evidence_ids)] if evidence_ids else list(fallback_evidence_ids)

    if not normalized["evidence_ids"] and fallback_evidence_ids:
        normalized["evidence_ids"] = list(fallback_evidence_ids)

    return normalized


LocalLLMClient = OpenAICompatibleLLMClient


def _normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
