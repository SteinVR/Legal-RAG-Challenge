"""Concrete Codex-backed provider for grounded free-text generation."""

from __future__ import annotations

import json
import logging
import math
import os
import time
from dataclasses import dataclass, field
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from src.common.runtime_logging import get_logger, log_event

DEFAULT_CODEX_BASE_URL = "https://api.openai.com/v1"
DEFAULT_CODEX_MODEL = "gpt-5.4-mini"
DEFAULT_PROVIDER_CONFIDENCE = 0.5
DEFAULT_MAX_OUTPUT_TOKENS = 220
LOGGER = get_logger("providers.codex")

_SYSTEM_PROMPT = (
    "Answer strictly from the provided legal evidence. "
    "Return exactly one JSON object with keys: answer (string) and confidence (number from 0 to 1). "
    "Do not include markdown or additional keys."
)
_STRUCTURED_SYSTEM_PROMPT = (
    "Answer strictly from the provided legal evidence and return one JSON object that follows the supplied schema. "
    "Use null only when the schema permits null and the evidence is insufficient."
)


@dataclass(slots=True)
class CodexFreeTextProvider:
    """HTTP provider that calls a Codex-compatible `/responses` endpoint."""

    model: str = DEFAULT_CODEX_MODEL
    base_url: str = DEFAULT_CODEX_BASE_URL
    api_key: str | None = None
    timeout_seconds: float = 60.0
    user_agent: str = "agentic-rag-challenge/0.1.0"
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS
    transport: httpx.BaseTransport | None = None
    _client: httpx.Client = field(init=False, repr=False)

    def __post_init__(self) -> None:
        token = _resolve_provider_token(self.api_key)
        if not token:
            raise ValueError(
                "Codex provider token is missing. Set CODEX_OAUTH_TOKEN, OPENAI_API_KEY, "
                "or pass api_key explicitly."
            )
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive.")
        if self.max_output_tokens <= 0:
            raise ValueError("max_output_tokens must be positive.")

        self._client = _build_http_client(
            token=token,
            base_url=self.base_url,
            user_agent=self.user_agent,
            timeout_seconds=self.timeout_seconds,
            transport=self.transport,
        )

    def generate(
        self,
        *,
        question: str,
        evidence_pages: list[dict[str, Any]],
        max_chars: int,
    ) -> dict[str, Any]:
        if max_chars <= 0:
            raise ValueError("max_chars must be positive.")
        started_at = time.perf_counter()

        response = self._client.post(
            "responses",
            json={
                "model": self.model,
                "input": [
                    {
                        "role": "system",
                        "content": [
                            {
                                "type": "input_text",
                                "text": _SYSTEM_PROMPT,
                            }
                        ],
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": _build_user_prompt(
                                    question=question,
                                    evidence_pages=evidence_pages,
                                    max_chars=max_chars,
                                ),
                            }
                        ],
                    },
                ],
                "max_output_tokens": self.max_output_tokens,
            },
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Provider response must be a JSON object.")

        response_text = _extract_response_text(payload)
        answer, confidence = _parse_answer_payload(response_text, max_chars=max_chars)
        result = {
            "answer": answer,
            "confidence": confidence,
        }
        log_event(
            LOGGER,
            logging.DEBUG,
            "provider.generate.complete",
            "Provider response received.",
            stage="answering",
            model=self.model,
            evidence_page_count=len(evidence_pages),
            max_chars=max_chars,
            duration_ms=round((time.perf_counter() - started_at) * 1000, 3),
            answer_chars=len(answer),
        )
        return result

    def generate_structured(
        self,
        *,
        question: str,
        answer_type: str,
        evidence_pages: list[dict[str, Any]],
        answer_schema: type[BaseModel],
        reasoning_effort: str,
    ) -> dict[str, Any]:
        started_at = time.perf_counter()
        normalized_effort = str(reasoning_effort).strip().lower() or "medium"
        schema_name = f"{answer_type}_answer"
        schema_payload = answer_schema.model_json_schema()

        response = self._client.post(
            "responses",
            json={
                "model": self.model,
                "reasoning": {"effort": normalized_effort},
                "input": [
                    {
                        "role": "system",
                        "content": [{"type": "input_text", "text": _STRUCTURED_SYSTEM_PROMPT}],
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": _build_structured_user_prompt(
                                    question=question,
                                    answer_type=answer_type,
                                    evidence_pages=evidence_pages,
                                ),
                            }
                        ],
                    },
                ],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": schema_name,
                        "schema": schema_payload,
                    },
                },
                "max_output_tokens": self.max_output_tokens,
            },
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Provider response must be a JSON object.")

        response_text = _extract_response_text(payload)
        structured = _parse_structured_payload(response_text)
        try:
            validated = answer_schema.model_validate(structured)
        except ValidationError as exc:
            raise ValueError("Structured provider output failed schema validation.") from exc

        result = dict(validated.model_dump())
        result["confidence"] = _coerce_confidence(structured.get("confidence", DEFAULT_PROVIDER_CONFIDENCE))
        log_event(
            LOGGER,
            logging.DEBUG,
            "provider.generate_structured.complete",
            "Structured provider response received.",
            stage="answering",
            model=self.model,
            answer_type=answer_type,
            evidence_page_count=len(evidence_pages),
            reasoning_effort=normalized_effort,
            duration_ms=round((time.perf_counter() - started_at) * 1000, 3),
        )
        return result

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "CodexFreeTextProvider":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


@dataclass(slots=True)
class CodexStructuredOutputProvider:
    """HTTP provider that requests schema-bound structured outputs."""

    model: str = DEFAULT_CODEX_MODEL
    base_url: str = DEFAULT_CODEX_BASE_URL
    api_key: str | None = None
    timeout_seconds: float = 60.0
    user_agent: str = "agentic-rag-challenge/0.1.0"
    transport: httpx.BaseTransport | None = None
    _client: httpx.Client = field(init=False, repr=False)

    def __post_init__(self) -> None:
        token = _resolve_provider_token(self.api_key)
        if not token:
            raise ValueError(
                "Codex provider token is missing. Set CODEX_OAUTH_TOKEN, OPENAI_API_KEY, "
                "or pass api_key explicitly."
            )
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive.")
        self._client = _build_http_client(
            token=token,
            base_url=self.base_url,
            user_agent=self.user_agent,
            timeout_seconds=self.timeout_seconds,
            transport=self.transport,
        )

    def generate_structured(
        self,
        *,
        schema_name: str,
        schema: dict[str, object],
        system_prompt: str,
        user_prompt: str,
        max_output_tokens: int,
        reasoning_effort: str = "medium",
    ) -> dict[str, Any]:
        if max_output_tokens <= 0:
            raise ValueError("max_output_tokens must be positive.")

        response = self._client.post(
            "responses",
            json={
                "model": self.model,
                "input": [
                    {
                        "role": "system",
                        "content": [{"type": "input_text", "text": system_prompt}],
                    },
                    {
                        "role": "user",
                        "content": [{"type": "input_text", "text": user_prompt}],
                    },
                ],
                "reasoning": {"effort": reasoning_effort},
                "text": {
                    "format": {
                        "type": "json_schema",
                        "name": schema_name,
                        "schema": schema,
                        "strict": True,
                    }
                },
                "max_output_tokens": max_output_tokens,
            },
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Provider response must be a JSON object.")

        response_text = _extract_response_text(payload)
        try:
            parsed = json.loads(response_text)
        except json.JSONDecodeError as exc:
            raise ValueError("Provider structured payload is not valid JSON.") from exc
        if not isinstance(parsed, dict):
            raise ValueError("Provider structured payload must be a JSON object.")
        return parsed

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "CodexStructuredOutputProvider":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def _build_http_client(
    *,
    token: str,
    base_url: str,
    user_agent: str,
    timeout_seconds: float,
    transport: httpx.BaseTransport | None,
) -> httpx.Client:
    return httpx.Client(
        base_url=base_url.rstrip("/") + "/",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": user_agent,
        },
        timeout=httpx.Timeout(timeout_seconds),
        follow_redirects=True,
        transport=transport,
    )


def _resolve_provider_token(explicit_token: str | None) -> str:
    candidates = [
        explicit_token,
        os.getenv("CODEX_OAUTH_TOKEN"),
        os.getenv("OPENAI_API_KEY"),
        os.getenv("CODEX_API_KEY"),
    ]
    for candidate in candidates:
        token = (candidate or "").strip()
        if token:
            return token
    return ""


def _format_page_reference(page: dict[str, Any]) -> str:
    page_numbers = page.get("page_numbers")
    if isinstance(page_numbers, list):
        normalized_page_numbers: list[str] = []
        for page_number in page_numbers:
            try:
                parsed_page = int(page_number)
            except (TypeError, ValueError):
                continue
            if parsed_page > 0:
                normalized_page_numbers.append(str(parsed_page))
        return ",".join(normalized_page_numbers)

    page_number = page.get("page_number")
    if page_number is None:
        return ""
    try:
        parsed_page = int(page_number)
    except (TypeError, ValueError):
        return ""
    return str(parsed_page) if parsed_page > 0 else ""


def _build_user_prompt(*, question: str, evidence_pages: list[dict[str, Any]], max_chars: int) -> str:
    evidence_lines: list[str] = []
    for index, page in enumerate(evidence_pages, start=1):
        doc_id = str(page.get("doc_id") or "").strip()
        page_ref = _format_page_reference(page)
        text = _normalize_whitespace(str(page.get("text") or ""))
        evidence_lines.append(f"[{index}] doc_id={doc_id}; pages={page_ref}; text={text}")

    evidence_blob = "\n".join(evidence_lines) if evidence_lines else "(no evidence)"
    return (
        f"Question: {_normalize_whitespace(question)}\n"
        f"Answer max length: {max_chars} characters.\n"
        "Evidence:\n"
        f"{evidence_blob}"
    )


def _build_structured_user_prompt(*, question: str, answer_type: str, evidence_pages: list[dict[str, Any]]) -> str:
    evidence_lines: list[str] = []
    for index, page in enumerate(evidence_pages, start=1):
        doc_id = str(page.get("doc_id") or "").strip()
        page_ref = _format_page_reference(page)
        text = _normalize_whitespace(str(page.get("text") or ""))
        evidence_lines.append(f"[{index}] doc_id={doc_id}; pages={page_ref}; text={text}")

    evidence_blob = "\n".join(evidence_lines) if evidence_lines else "(no evidence)"
    return (
        f"Answer type: {_normalize_whitespace(answer_type)}\n"
        f"Question: {_normalize_whitespace(question)}\n"
        "Evidence:\n"
        f"{evidence_blob}"
    )


def _extract_response_text(payload: dict[str, Any]) -> str:
    output_text = payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text

    output = payload.get("output")
    if isinstance(output, list):
        chunks: list[str] = []
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for content_item in content:
                if not isinstance(content_item, dict):
                    continue
                text = content_item.get("text")
                if isinstance(text, str) and text.strip():
                    chunks.append(text)
        if chunks:
            return "\n".join(chunks)

    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                return content
            if isinstance(content, list):
                text_chunks: list[str] = []
                for part in content:
                    if isinstance(part, dict) and isinstance(part.get("text"), str):
                        text_chunks.append(part["text"])
                if text_chunks:
                    return "\n".join(text_chunks)

    raise ValueError("Provider response does not contain readable text output.")


def _parse_answer_payload(response_text: str, *, max_chars: int) -> tuple[str, float]:
    normalized = _normalize_whitespace(response_text)
    if not normalized:
        raise ValueError("Provider returned an empty answer payload.")

    answer = normalized
    confidence = DEFAULT_PROVIDER_CONFIDENCE
    try:
        parsed = json.loads(normalized)
    except json.JSONDecodeError:
        parsed = None

    if isinstance(parsed, dict):
        raw_answer = parsed.get("answer")
        if raw_answer is None:
            raise ValueError("Provider JSON payload must include an answer field.")
        answer = _normalize_whitespace(str(raw_answer))
        confidence = _coerce_confidence(parsed.get("confidence", DEFAULT_PROVIDER_CONFIDENCE))

    if len(answer) > max_chars:
        answer = answer[:max_chars].rstrip()
    if not answer:
        raise ValueError("Provider produced an empty answer after normalization.")

    return answer, confidence


def _parse_structured_payload(response_text: str) -> dict[str, Any]:
    normalized = _normalize_whitespace(response_text)
    if not normalized:
        raise ValueError("Provider returned an empty structured payload.")
    try:
        parsed = json.loads(normalized)
    except json.JSONDecodeError as exc:
        raise ValueError("Provider structured payload must be valid JSON.") from exc
    if not isinstance(parsed, dict):
        raise ValueError("Provider structured payload must be a JSON object.")
    return parsed


def _coerce_confidence(raw_confidence: Any) -> float:
    try:
        confidence = float(raw_confidence)
    except (TypeError, ValueError):
        return DEFAULT_PROVIDER_CONFIDENCE
    if not math.isfinite(confidence):
        return DEFAULT_PROVIDER_CONFIDENCE
    if confidence < 0.0 or confidence > 1.0:
        return DEFAULT_PROVIDER_CONFIDENCE
    return confidence


def _normalize_whitespace(value: str) -> str:
    return " ".join(value.split())
