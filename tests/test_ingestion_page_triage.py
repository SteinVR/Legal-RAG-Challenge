from __future__ import annotations

from src.common.config import IngestionSettings
from src.common.schemas import TriageLabel
from src.ingestion.page_triage import PageSignals, classify_page, compute_quality_score


def test_classify_page_returns_scan_for_low_text() -> None:
    settings = IngestionSettings()
    signals = PageSignals(
        page_number=1,
        text_char_count=1,
        word_count=1,
        image_block_count=0,
        max_image_area_ratio=0.0,
        drawing_count=0,
        table_count=0,
        bad_char_ratio=0.0,
        legal_marker_hits=[],
    )

    label, flags = classify_page(signals, settings)

    assert label is TriageLabel.SCAN
    assert "low_text" in flags


def test_classify_page_returns_suspicious_for_encoding_noise() -> None:
    settings = IngestionSettings()
    signals = PageSignals(
        page_number=1,
        text_char_count=120,
        word_count=20,
        image_block_count=0,
        max_image_area_ratio=0.1,
        drawing_count=0,
        table_count=0,
        bad_char_ratio=0.25,
        legal_marker_hits=["article"],
    )

    label, flags = classify_page(signals, settings)

    assert label is TriageLabel.SUSPICIOUS
    assert "bad_encoding" in flags


def test_compute_quality_score_uses_weighted_components() -> None:
    settings = IngestionSettings(text_completeness_target_chars=1000, encoding_bad_char_threshold=0.1)
    signals = PageSignals(
        page_number=1,
        text_char_count=500,
        word_count=20,
        image_block_count=0,
        max_image_area_ratio=0.0,
        drawing_count=0,
        table_count=0,
        bad_char_ratio=0.02,
        legal_marker_hits=["article", "regulation"],
    )

    assert compute_quality_score(signals, settings) == 0.6233
