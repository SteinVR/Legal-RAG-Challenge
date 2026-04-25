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

    model_name = "no-api-smoke-provider"

    def generate_structured(
        self,
        *,
        question: str,
        answer_type: str,
        evidence_pages: list[dict[str, Any]],
        **_: Any,
    ) -> dict[str, Any]:
        """Return a compact structured answer from synthetic smoke evidence."""

        evidence_text = " ".join(str(page.get("text") or "") for page in evidence_pages)
        normalized = normalize_compact_text(evidence_text)
        final_answer = _smoke_answer(question=question, answer_type=answer_type, evidence_text=normalized)
        if final_answer is None:
            return {
                "is_answerable": False,
                "final_answer": None,
                "relevant_evidence_indices": [],
                "relevant_pages": [],
                "reasoning_summary": "No supporting text found.",
                "confidence": 0.0,
            }

        all_indices = list(range(1, len(evidence_pages) + 1))
        return {
            "is_answerable": True,
            "final_answer": final_answer,
            "relevant_evidence_indices": all_indices,
            "relevant_pages": _relevant_pages_for_indices(evidence_pages=evidence_pages, indices=all_indices),
            "reasoning_summary": "Deterministic local smoke answer from provided evidence.",
            "confidence": 0.8 if answer_type == "free_text" else 1.0,
        }


def _smoke_answer(*, question: str, answer_type: str, evidence_text: str) -> Any:
    """Resolve simple answers for synthetic smoke fixtures only."""

    if not evidence_text:
        return None
    question_lower = question.casefold()
    if answer_type == "free_text":
        return evidence_text[:280]
    if answer_type == "boolean":
        return True
    if answer_type == "date":
        return "2025-12-19"
    if answer_type == "number":
        return 2 if "law number" in question_lower else 30
    if answer_type == "names":
        return ["OLEXA"] if "listed" in question_lower else ["Obasi"]
    if answer_type == "name":
        return "OLEXA" if "listed" in question_lower else "Obasi"
    return None


def _relevant_pages_for_indices(*, evidence_pages: list[dict[str, Any]], indices: list[int]) -> list[int]:
    """Collect sorted page numbers for selected evidence indices."""

    selected = set(indices)
    return sorted(
        {
            int(page_number)
            for index, page in enumerate(evidence_pages, start=1)
            if index in selected
            for page_number in page.get("page_numbers", [page.get("page_number")])
            if page_number is not None
        }
    )


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
