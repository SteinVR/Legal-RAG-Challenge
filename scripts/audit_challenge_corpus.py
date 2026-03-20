#!/usr/bin/env python3
"""Audit locally downloaded challenge PDFs and emit a JSON summary."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import math
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from zipfile import ZipFile

import fitz

EXTRACTABLE_TEXT_MIN_CHARS = 50
LARGE_IMAGE_AREA_RATIO = 0.25
SCAN_IMAGE_AREA_RATIO = 0.70


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--documents-dir", type=Path, required=True, help="Directory with extracted PDFs.")
    parser.add_argument("--output", type=Path, required=True, help="Path to write the audit JSON.")
    parser.add_argument("--phase", type=str, default="unknown", help="Logical phase label.")
    parser.add_argument("--archive-path", type=Path, default=None, help="Optional documents zip path.")
    parser.add_argument("--questions-path", type=Path, default=None, help="Optional questions JSON path.")
    parser.add_argument("--manifest-path", type=Path, default=None, help="Optional sync manifest JSON path.")
    parser.add_argument("--data-root", type=Path, default=None, help="Optional data root for phase coverage audit.")
    return parser.parse_args()


def percentile(values: list[float], ratio: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    index = (len(ordered) - 1) * ratio
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return ordered[int(index)]
    weight = index - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def round_or_none(value: float | None, digits: int = 3) -> float | None:
    return None if value is None else round(value, digits)


def summarize_numbers(values: list[int | float]) -> dict[str, int | float | None]:
    if not values:
        return {
            "count": 0,
            "min": None,
            "mean": None,
            "median": None,
            "p10": None,
            "p90": None,
            "max": None,
        }

    total = sum(values)
    return {
        "count": len(values),
        "min": min(values),
        "mean": round(total / len(values), 3),
        "median": round_or_none(float(median(values))),
        "p10": round_or_none(percentile([float(v) for v in values], 0.10)),
        "p90": round_or_none(percentile([float(v) for v in values], 0.90)),
        "max": max(values),
    }


def classify_document_family(first_page_heading: str) -> str:
    heading = first_page_heading.upper()

    if "LAW NO." in heading or "DIFC LAW" in heading or heading.endswith(" LAW"):
        return "law_or_regulation"

    court_markers = [
        "COURT OF",
        "SCT",
        "ARBITRATION",
        "DIGITAL ECONOMY COURT",
        "TECHNOLOGY AND CONSTRUCTION DIVISION",
        "ENFORCEMENT",
        "JUDGMENTS",
        "ORDERS",
    ]
    if any(marker in heading for marker in court_markers):
        return "court_or_arbitration_decision"

    return "other_legal_document"


def relative_to_repo(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)


def load_json(path: Path | None) -> dict | list | None:
    if path is None or not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def audit_archive(archive_path: Path | None) -> dict | None:
    if archive_path is None or not archive_path.exists():
        return None

    with ZipFile(archive_path) as archive:
        entries = [name for name in archive.namelist() if not name.endswith("/")]

    extensions = Counter(Path(name).suffix.lower() or "<no_ext>" for name in entries)
    return {
        "path": relative_to_repo(archive_path),
        "size_bytes": archive_path.stat().st_size,
        "entry_count": len(entries),
        "extensions": dict(sorted(extensions.items())),
        "first_entries": entries[:10],
    }


def audit_questions(questions_path: Path | None) -> dict | None:
    payload = load_json(questions_path)
    if payload is None:
        return None
    if not isinstance(payload, list):
        raise ValueError(f"Expected questions payload to be a list: {questions_path}")

    answer_types = Counter(str(item.get("answer_type")) for item in payload if isinstance(item, dict))
    return {
        "path": relative_to_repo(questions_path),
        "count": len(payload),
        "answer_types": dict(sorted(answer_types.items())),
        "sample_question_ids": [item.get("id") for item in payload[:5] if isinstance(item, dict)],
    }


def audit_phase_coverage(data_root: Path | None) -> dict | None:
    if data_root is None or not data_root.exists():
        return None

    phase_summary: dict[str, dict[str, int | bool]] = {}
    for phase_dir in sorted(path for path in data_root.iterdir() if path.is_dir()):
        files = [path for path in phase_dir.rglob("*") if path.is_file() and path.name != ".gitkeep"]
        pdf_count = sum(1 for path in files if path.suffix.lower() == ".pdf")
        json_count = sum(1 for path in files if path.suffix.lower() == ".json")
        zip_count = sum(1 for path in files if path.suffix.lower() == ".zip")
        phase_summary[phase_dir.name] = {
            "non_placeholder_file_count": len(files),
            "pdf_count": pdf_count,
            "json_count": json_count,
            "zip_count": zip_count,
            "has_manifest": any(path.name == "sync_manifest.json" for path in files),
            "has_questions_json": any(path.name == "questions.json" for path in files),
        }

    return phase_summary


def audit_documents(documents_dir: Path) -> dict:
    fitz.TOOLS.mupdf_display_warnings(False)
    fitz.TOOLS.mupdf_display_errors(False)

    pdf_paths = sorted(path for path in documents_dir.rglob("*.pdf") if path.is_file())
    if not pdf_paths:
        raise ValueError(f"No PDFs found in {documents_dir}")

    family_counts: Counter[str] = Counter()
    page_text_char_counts: list[int] = []
    page_word_counts: list[int] = []
    page_max_image_area_ratios: list[float] = []
    page_image_block_counts: list[int] = []
    page_table_counts: list[int] = []
    page_drawing_counts: list[int] = []
    suspicious_pages: list[dict[str, int | float | str | bool]] = []
    documents: list[dict[str, int | float | str | bool]] = []

    for pdf_path in pdf_paths:
        with fitz.open(pdf_path) as document:
            first_page_text = document[0].get_text("text") if document.page_count else ""
            first_lines = [line.strip() for line in first_page_text.splitlines() if line.strip()]
            first_heading = " | ".join(first_lines[:4])[:240]
            family = classify_document_family(first_heading)
            family_counts[family] += 1

            metadata = document.metadata or {}
            toc_entries = document.get_toc(simple=False)
            file_size_bytes = pdf_path.stat().st_size

            doc_text_chars: list[int] = []
            doc_image_area_ratios: list[float] = []
            doc_image_pages = 0
            doc_large_image_pages = 0
            doc_extractable_text_pages = 0
            doc_low_text_pages = 0
            doc_no_text_pages = 0
            doc_likely_scan_pages = 0
            doc_likely_ocr_backed_pages = 0
            doc_table_pages = 0
            doc_tables_detected = 0

            for page_index in range(document.page_count):
                page = document[page_index]
                page_text = page.get_text("text")
                text_char_count = len(page_text.strip())
                word_count = len(page_text.split())
                raw_page = page.get_text("rawdict")
                blocks = raw_page.get("blocks", [])
                image_blocks = [block for block in blocks if block.get("type") == 1]
                page_area = max(page.rect.width * page.rect.height, 1.0)
                image_area_ratios = []
                for block in image_blocks:
                    x0, y0, x1, y1 = block["bbox"]
                    image_area = max((x1 - x0) * (y1 - y0), 0.0)
                    image_area_ratios.append(image_area / page_area)

                max_image_area_ratio = max(image_area_ratios, default=0.0)
                drawing_count = len(page.get_drawings())
                try:
                    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                        table_count = len(page.find_tables().tables)
                except Exception:
                    table_count = 0

                extractable_text = text_char_count >= EXTRACTABLE_TEXT_MIN_CHARS
                low_text = text_char_count < EXTRACTABLE_TEXT_MIN_CHARS
                no_text = text_char_count == 0
                large_image = max_image_area_ratio >= LARGE_IMAGE_AREA_RATIO
                likely_scan = max_image_area_ratio >= SCAN_IMAGE_AREA_RATIO and low_text
                likely_ocr_backed_scan = max_image_area_ratio >= SCAN_IMAGE_AREA_RATIO and extractable_text

                page_text_char_counts.append(text_char_count)
                page_word_counts.append(word_count)
                page_max_image_area_ratios.append(max_image_area_ratio)
                page_image_block_counts.append(len(image_blocks))
                page_table_counts.append(table_count)
                page_drawing_counts.append(drawing_count)
                doc_text_chars.append(text_char_count)
                doc_image_area_ratios.append(max_image_area_ratio)

                if image_blocks:
                    doc_image_pages += 1
                if large_image:
                    doc_large_image_pages += 1
                if extractable_text:
                    doc_extractable_text_pages += 1
                if low_text:
                    doc_low_text_pages += 1
                if no_text:
                    doc_no_text_pages += 1
                if likely_scan:
                    doc_likely_scan_pages += 1
                if likely_ocr_backed_scan:
                    doc_likely_ocr_backed_pages += 1
                if table_count > 0:
                    doc_table_pages += 1
                    doc_tables_detected += table_count

                if low_text or large_image or table_count > 0:
                    suspicious_pages.append(
                        {
                            "doc_id": pdf_path.stem,
                            "page_number": page_index + 1,
                            "text_char_count": text_char_count,
                            "word_count": word_count,
                            "image_block_count": len(image_blocks),
                            "max_image_area_ratio": round(max_image_area_ratio, 4),
                            "drawing_count": drawing_count,
                            "table_count": table_count,
                            "low_text": low_text,
                            "large_image": large_image,
                            "likely_scan": likely_scan,
                            "likely_ocr_backed_scan": likely_ocr_backed_scan,
                        }
                    )

            documents.append(
                {
                    "doc_id": pdf_path.stem,
                    "relative_path": relative_to_repo(pdf_path),
                    "file_size_bytes": file_size_bytes,
                    "page_count": document.page_count,
                    "inferred_family": family,
                    "first_page_heading": first_heading,
                    "pdf_title_metadata": (metadata.get("title") or "").strip() or None,
                    "toc_entries": len(toc_entries),
                    "extractable_text_pages": doc_extractable_text_pages,
                    "low_text_pages": doc_low_text_pages,
                    "no_text_pages": doc_no_text_pages,
                    "image_pages": doc_image_pages,
                    "large_image_pages": doc_large_image_pages,
                    "likely_scan_pages": doc_likely_scan_pages,
                    "likely_ocr_backed_scan_pages": doc_likely_ocr_backed_pages,
                    "table_pages": doc_table_pages,
                    "tables_detected": doc_tables_detected,
                    "text_char_count_total": sum(doc_text_chars),
                    "text_char_count_median_per_page": round_or_none(float(median(doc_text_chars))),
                    "max_image_area_ratio": round(max(doc_image_area_ratios, default=0.0), 4),
                }
            )

    total_pages = sum(int(document["page_count"]) for document in documents)
    docs_with_title_metadata = sum(1 for document in documents if document["pdf_title_metadata"])
    docs_with_toc = sum(1 for document in documents if int(document["toc_entries"]) > 0)
    docs_with_images = sum(1 for document in documents if int(document["image_pages"]) > 0)
    docs_with_tables = sum(1 for document in documents if int(document["table_pages"]) > 0)
    docs_with_likely_scans = sum(1 for document in documents if int(document["likely_scan_pages"]) > 0)
    docs_all_pages_extractable = sum(
        1 for document in documents if int(document["extractable_text_pages"]) == int(document["page_count"])
    )

    return {
        "documents_dir": relative_to_repo(documents_dir),
        "pdf_count": len(documents),
        "total_pages": total_pages,
        "document_family_counts": dict(sorted(family_counts.items())),
        "docs_with_title_metadata": docs_with_title_metadata,
        "docs_with_toc": docs_with_toc,
        "docs_with_images": docs_with_images,
        "docs_with_tables": docs_with_tables,
        "docs_with_likely_scans": docs_with_likely_scans,
        "docs_all_pages_extractable_text": docs_all_pages_extractable,
        "page_count_stats": summarize_numbers([int(document["page_count"]) for document in documents]),
        "file_size_bytes_stats": summarize_numbers([int(document["file_size_bytes"]) for document in documents]),
        "page_text_char_stats": summarize_numbers(page_text_char_counts),
        "page_word_stats": summarize_numbers(page_word_counts),
        "page_image_block_stats": summarize_numbers(page_image_block_counts),
        "page_max_image_area_ratio_stats": summarize_numbers(page_max_image_area_ratios),
        "page_table_count_stats": summarize_numbers(page_table_counts),
        "page_drawing_count_stats": summarize_numbers(page_drawing_counts),
        "page_level_counts": {
            "extractable_text_pages": sum(
                1 for value in page_text_char_counts if value >= EXTRACTABLE_TEXT_MIN_CHARS
            ),
            "low_text_pages": sum(1 for value in page_text_char_counts if value < EXTRACTABLE_TEXT_MIN_CHARS),
            "no_text_pages": sum(1 for value in page_text_char_counts if value == 0),
            "pages_with_images": sum(1 for value in page_image_block_counts if value > 0),
            "pages_with_large_images": sum(
                1 for value in page_max_image_area_ratios if value >= LARGE_IMAGE_AREA_RATIO
            ),
            "likely_scan_pages": sum(
                1
                for text_chars, image_ratio in zip(page_text_char_counts, page_max_image_area_ratios, strict=True)
                if text_chars < EXTRACTABLE_TEXT_MIN_CHARS and image_ratio >= SCAN_IMAGE_AREA_RATIO
            ),
            "likely_ocr_backed_scan_pages": sum(
                1
                for text_chars, image_ratio in zip(page_text_char_counts, page_max_image_area_ratios, strict=True)
                if text_chars >= EXTRACTABLE_TEXT_MIN_CHARS and image_ratio >= SCAN_IMAGE_AREA_RATIO
            ),
            "pages_with_tables": sum(1 for value in page_table_counts if value > 0),
            "total_tables_detected": sum(page_table_counts),
        },
        "heuristics": {
            "extractable_text_min_chars": EXTRACTABLE_TEXT_MIN_CHARS,
            "large_image_area_ratio": LARGE_IMAGE_AREA_RATIO,
            "scan_image_area_ratio": SCAN_IMAGE_AREA_RATIO,
            "table_detection_note": "PyMuPDF table detection is conservative and may miss borderless tables.",
        },
        "top_documents_by_pages": [
            {
                "doc_id": document["doc_id"],
                "page_count": document["page_count"],
                "inferred_family": document["inferred_family"],
                "first_page_heading": document["first_page_heading"],
            }
            for document in sorted(documents, key=lambda item: (-int(item["page_count"]), str(item["doc_id"])))[:10]
        ],
        "top_documents_by_tables": [
            {
                "doc_id": document["doc_id"],
                "table_pages": document["table_pages"],
                "tables_detected": document["tables_detected"],
                "first_page_heading": document["first_page_heading"],
            }
            for document in sorted(
                documents,
                key=lambda item: (-int(item["tables_detected"]), -int(item["table_pages"]), str(item["doc_id"])),
            )[:10]
            if int(document["tables_detected"]) > 0
        ],
        "suspicious_pages_sample": sorted(
            suspicious_pages,
            key=lambda item: (
                not bool(item["likely_scan"]),
                not bool(item["large_image"]),
                not bool(item["low_text"]),
                -int(item["table_count"]),
                str(item["doc_id"]),
                int(item["page_number"]),
            ),
        )[:100],
        "documents": documents,
    }


def main() -> int:
    args = parse_args()

    audit = {
        "generated_at": datetime.now(UTC).isoformat(),
        "phase": args.phase,
        "archive": audit_archive(args.archive_path),
        "questions": audit_questions(args.questions_path),
        "manifest": load_json(args.manifest_path),
        "phase_coverage": audit_phase_coverage(args.data_root),
        "document_audit": audit_documents(args.documents_dir),
    }

    if audit["archive"] is not None:
        archive_entries = int(audit["archive"]["entry_count"])
        pdf_count = int(audit["document_audit"]["pdf_count"])
        audit["download_integrity"] = {
            "archive_entries_match_extracted_pdfs": archive_entries == pdf_count,
            "archive_entry_count": archive_entries,
            "extracted_pdf_count": pdf_count,
            "manifest_extracted_pdf_count": (
                audit["manifest"].get("extracted_pdf_count")
                if isinstance(audit["manifest"], dict)
                else None
            ),
            "manifest_questions_count": (
                audit["manifest"].get("questions_count") if isinstance(audit["manifest"], dict) else None
            ),
        }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(relative_to_repo(args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
