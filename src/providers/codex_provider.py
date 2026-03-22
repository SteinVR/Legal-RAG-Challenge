"""Concrete Codex-backed provider for grounded free-text generation."""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field
from typing import Any

import httpx

DEFAULT_CODEX_BASE_URL = "https://api.openai.com/v1"
DEFAULT_CODEX_MODEL = "gpt-5-mini"
DEFAULT_PROVIDER_CONFIDENCE = 0.5
DEFAULT_MAX_OUTPUT_TOKENS = 220

_SYSTEM_PROMPT = (
    "Answer strictly from the provided legal evidence. "
    "Return exactly one JSON object with keys: answer (string) and confidence (number from 0 to 1). "
    "Do not include markdown or additional keys."
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

        self._client = httpx.Client(
            base_url=self.base_url.rstrip("/") + "/",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": self.user_agent,
            },
            timeout=httpx.Timeout(self.timeout_seconds),
            follow_redirects=True,
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
        return {
            "answer": answer,
            "confidence": confidence,
        }

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "CodexFreeTextProvider":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


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


def _build_user_prompt(*, question: str, evidence_pages: list[dict[str, Any]], max_chars: int) -> str:
    evidence_lines: list[str] = []
    for index, page in enumerate(evidence_pages, start=1):
        doc_id = str(page.get("doc_id") or "").strip()
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
            page_ref = ",".join(normalized_page_numbers)
        else:
            page_number = page.get("page_number")
            if page_number is None:
                page_ref = ""
            else:
                try:
                    parsed_page = int(page_number)
                except (TypeError, ValueError):
                    parsed_page = 0
                page_ref = str(parsed_page) if parsed_page > 0 else ""
        text = _normalize_whitespace(str(page.get("text") or ""))
        evidence_lines.append(f"[{index}] doc_id={doc_id}; pages={page_ref}; text={text}")

    evidence_blob = "\n".join(evidence_lines) if evidence_lines else "(no evidence)"
    return (
        f"Question: {_normalize_whitespace(question)}\n"
        f"Answer max length: {max_chars} characters.\n"
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
