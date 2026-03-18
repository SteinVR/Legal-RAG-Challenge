"""Shared typed models for the foundation layer."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Phase(StrEnum):
    """Competition phases supported by the local workspace."""

    WARMUP = "warmup"
    FINAL = "final"


class QuestionRecord(BaseModel):
    """Question payload returned by the competition API."""

    model_config = ConfigDict(extra="forbid")

    id: str
    question: str
    answer_type: str


class ArtifactMetadata(BaseModel):
    """Persisted metadata for a local phase artifact."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["file", "directory"]
    relative_path: str
    sha256: str | None = None
    size_bytes: int | None = None
    file_count: int | None = None
    updated_at: datetime | None = None


class PhaseSyncManifest(BaseModel):
    """Manifest describing the current local state for a phase sync."""

    model_config = ConfigDict(extra="forbid")

    phase: Phase
    phase_isolation: Literal["local-only"] = "local-only"
    synced_at: datetime
    base_url: str
    api_key_env: str
    operations: list[str] = Field(default_factory=list)
    questions_count: int | None = None
    extracted_pdf_count: int | None = None
    artifacts: dict[str, ArtifactMetadata] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
