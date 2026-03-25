from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import fitz


def write_json(path: Path, payload: Any, *, indent: int = 2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=indent) + "\n", encoding="utf-8")


def write_jsonl(path: Path, records: Iterable[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            serialized = record.model_dump(mode="json") if hasattr(record, "model_dump") else record
            handle.write(json.dumps(serialized, ensure_ascii=False))
            handle.write("\n")


def write_questions(path: Path, questions: list[dict[str, Any]]) -> None:
    write_json(path, questions)


def write_pdf(
    path: Path,
    *,
    page_texts: list[str] | None = None,
    page_count: int | None = None,
    title: str | None = None,
    fill_prefix: str | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    texts = list(page_texts or [])
    if page_count is None:
        page_count = len(texts)
    if page_count is None or page_count < 1:
        raise ValueError("write_pdf requires at least one page via page_texts or page_count")

    document = fitz.open()
    for page_index in range(page_count):
        page = document.new_page()
        if page_index < len(texts):
            text = texts[page_index]
        elif fill_prefix is not None:
            text = f"{fill_prefix}{page_index + 1}"
        else:
            text = ""
        if text:
            page.insert_text((72, 72), text)
    if title:
        document.set_metadata({"title": title})
    document.save(path)
    document.close()
