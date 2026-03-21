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

