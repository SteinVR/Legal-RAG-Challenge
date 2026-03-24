"""Minimal page-attribution contract used by downstream telemetry and retrieval integration."""

from __future__ import annotations

from dataclasses import dataclass, field

from src.evaluation.contracts import PageReference


@dataclass(slots=True)
class PageAttributionTrace:
    """Stable page-attribution trace emitted by the W4A answer flow."""

    raw_retrieved_chunk_pages: list[PageReference] = field(default_factory=list)
    pass_a_pages: list[PageReference] = field(default_factory=list)
    solver_reported_pages: list[PageReference] = field(default_factory=list)
    final_emitted_pages: list[PageReference] = field(default_factory=list)
    validation_action: str = "none"
    collapsed_answer: bool = False
