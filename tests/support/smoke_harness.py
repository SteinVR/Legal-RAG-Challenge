"""Shared helpers for stage-level smoke testing."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.common.config import AppConfig

from .documents import write_pdf

SYNTHETIC_DOC_ID = "synthetic_law"
SYNTHETIC_PAGE_TEXTS = [
    "DIFC Employment Law\nArticle 8\nThe notice must be filed within 30 days.",
    "Article 9\nThe penalty amount is AED 1000 for late filing.",
]


@dataclass(slots=True, frozen=True)
class SyntheticFixture:
    """Synthetic local runtime fixture used by smoke tests."""

    config: AppConfig
    root_dir: Path
    documents_dir: Path
    document_id: str


class DeterministicDenseEmbedder:
    """Small deterministic embedder used to keep smoke tests offline and stable."""

    model_name = "deterministic-test-embedder"
    normalize_embeddings = True

    def __init__(self, *, prompt_name: str | None = "document") -> None:
        self.prompt_name = prompt_name

    def encode(self, texts: list[str]) -> list[list[float]]:
        """Encode text into deterministic vectors without external dependencies."""

        vectors: list[list[float]] = []
        for text in texts:
            normalized = normalize_compact_text(text)
            token_count = max(len(normalized.split()), 1)
            ordinal_sum = sum(ord(char) for char in normalized)
            vectors.append(
                [
                    float(token_count),
                    float((ordinal_sum % 997) + 1),
                    float((len(normalized) % 31) + 1),
                ]
            )
        return vectors


class NoApiProvider:
    """Provider stub that guarantees no OpenAI API calls in smoke tests."""

    supports_structured = False

    def generate(self, *, question: str, evidence_pages: list[dict[str, Any]], max_chars: int) -> dict[str, Any]:
        """Build a deterministic free-text answer from provided evidence only."""

        del question
        evidence_text = " ".join(str(page.get("text") or "") for page in evidence_pages)
        normalized = normalize_compact_text(evidence_text)
        answer = normalized[:max_chars] if normalized else "No supporting text found."
        return {"answer": answer, "confidence": 0.2}

    def generate_structured(self, **_: Any) -> dict[str, Any]:
        """Reject structured calls because smoke tests must avoid provider execution."""

        raise AssertionError("Structured provider calls are disabled in smoke tests.")


def prepare_synthetic_fixture(tmp_path: Path) -> SyntheticFixture:
    """Create a synthetic document fixture and return an aligned smoke config."""

    root_dir = tmp_path / "data"
    documents_dir = root_dir / "warmup" / "documents" / "pdfs"
    documents_dir.mkdir(parents=True, exist_ok=True)
    write_pdf(
        documents_dir / f"{SYNTHETIC_DOC_ID}.pdf",
        page_texts=SYNTHETIC_PAGE_TEXTS,
        title="Synthetic Employment Law",
    )
    config = build_smoke_config(root_dir)
    return SyntheticFixture(
        config=config,
        root_dir=root_dir,
        documents_dir=documents_dir,
        document_id=SYNTHETIC_DOC_ID,
    )


def build_smoke_config(root_dir: Path) -> AppConfig:
    """Build an offline-friendly warmup config for synthetic smoke tests."""

    return AppConfig.model_validate(
        {
            "phase": "warmup",
            "storage": {"root_dir": str(root_dir)},
            "download": {"overwrite": True},
            "ingestion": {
                "enable_ocr": False,
                "ocr_unavailable_policy": "degraded",
                "opendataloader_hybrid_backend": "off",
                "opendataloader_hybrid_fallback": True,
                "enable_semantic_table_blocks": False,
            },
            "logging": {"jsonl": False, "console": False},
        }
    )


def read_json(path: Path) -> Any:
    """Read a JSON file and return the decoded payload."""

    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read a JSONL file and return decoded line payloads."""

    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def normalize_compact_text(value: str) -> str:
    """Normalize text for stable assertions across whitespace differences."""

    return " ".join(str(value).split())

