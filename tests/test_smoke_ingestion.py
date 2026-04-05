"""Stage smoke for ingestion artifacts."""

from __future__ import annotations

from pathlib import Path

from src.ingestion.service import CorpusParseService
from src.submission.sync import PhasePaths
from tests.support.smoke_harness import prepare_synthetic_fixture, read_json, read_jsonl


def test_ingestion_smoke_creates_canonical_artifacts(tmp_path: Path) -> None:
    """Smoke-check parse-corpus by asserting real canonical artifact outputs."""

    fixture = prepare_synthetic_fixture(tmp_path)
    service = CorpusParseService(fixture.config)
    result = service.parse_corpus(overwrite=True)
    phase_paths = PhasePaths.from_config(fixture.config)
    raw_parse_dir = phase_paths.corpus_dir / "raw_parse"

    assert result.parsed_document_count == 1
    assert result.parsed_page_count == 2
    assert result.failed_document_count == 0

    assert phase_paths.corpus_path.exists()
    assert phase_paths.page_map_path.exists()
    assert phase_paths.corpus_manifest_path.exists()
    assert phase_paths.debug_dir.exists()
    assert (phase_paths.debug_dir / f"{fixture.document_id}.md").exists()
    assert (raw_parse_dir / "pymupdf" / f"{fixture.document_id}.json").exists()

    corpus_rows = read_jsonl(phase_paths.corpus_path)
    page_map_rows = read_json(phase_paths.page_map_path)
    manifest = read_json(phase_paths.corpus_manifest_path)

    assert len(corpus_rows) == 2
    assert any("30 days" in row["text"] for row in corpus_rows)
    assert len(page_map_rows) == 1
    assert page_map_rows[0]["doc_id"] == fixture.document_id
    assert page_map_rows[0]["page_numbers"] == [1, 2]
    assert manifest["document_count"] == 1
    assert manifest["page_count"] == 2
    assert manifest["failed_document_count"] == 0

