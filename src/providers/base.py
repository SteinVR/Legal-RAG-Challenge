"""Provider contracts for answer generation."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol


class FreeTextProvider(Protocol):
    """Minimal contract for grounded free-text generation."""

    def generate(
        self,
        *,
        question: str,
        evidence_pages: list[dict[str, Any]],
        max_chars: int,
    ) -> Mapping[str, Any]:
        """Generate a grounded answer with a confidence score."""


class StructuredOutputProvider(Protocol):
    """Minimal contract for schema-bound structured generation."""

    def generate_structured(
        self,
        *,
        schema_name: str,
        schema: dict[str, object],
        system_prompt: str,
        user_prompt: str,
        max_output_tokens: int,
        reasoning_effort: str = "medium",
    ) -> Mapping[str, Any]:
        """Generate a structured JSON payload that matches the provided schema."""
