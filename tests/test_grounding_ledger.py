"""Unit tests for recall-first grounding ledger post-processing."""

from __future__ import annotations

from pathlib import Path

from src.evaluation.contracts import AnswerType, PageReference, ReferenceAnswerRecord
from src.evaluation.grounding_ledger import (
    GroundingLedgerRow,
    build_grounding_ledger_rows,
    build_grounding_summary,
    build_top_failures_from_ledger_dir,
    write_grounding_ledger_csv,
)


def _reference(question_id: str, *, answer_type: AnswerType, pages: list[tuple[str, int]]) -> ReferenceAnswerRecord:
    """Build a compact benchmark reference fixture."""

    grouped: dict[str, list[int]] = {}
    for doc_id, page_number in pages:
        grouped.setdefault(doc_id, []).append(page_number)
    gold_retrieval = [
        PageReference(doc_id=doc_id, page_numbers=sorted(page_numbers))
        for doc_id, page_numbers in grouped.items()
    ]
    return ReferenceAnswerRecord(
        question_id=question_id,
        answer_type=answer_type,
        answer=None,
        question=f"Question {question_id}",
        gold_retrieval=gold_retrieval,
    )


def _answer(
    question_id: str,
    *,
    final: list[dict[str, object]],
    raw: list[dict[str, object]] | None = None,
    pass_a: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    """Build one submission answer fixture with retrieval telemetry layers."""

    retrieval = {"retrieved_chunk_pages": final}
    if raw is not None:
        retrieval["raw_retrieved_chunk_pages"] = raw
    if pass_a is not None:
        retrieval["pass_a_pages"] = pass_a
    return {"question_id": question_id, "answer": None, "telemetry": {"retrieval": retrieval}}


def _page_ref(doc_id: str, page: int) -> dict[str, object]:
    """Build one compact telemetry page reference payload."""

    return {"doc_id": doc_id, "page_numbers": [page]}


def test_build_grounding_ledger_rows_assigns_expected_buckets() -> None:
    """Validate raw/pass-a/final bucket assignment chain including `gold_empty`."""

    references = [
        _reference("q_raw_miss", answer_type=AnswerType.NUMBER, pages=[("doc_a", 1)]),
        _reference("q_pass_a_miss", answer_type=AnswerType.BOOLEAN, pages=[("doc_a", 1)]),
        _reference("q_final_miss", answer_type=AnswerType.DATE, pages=[("doc_a", 1)]),
        _reference("q_hit", answer_type=AnswerType.NAME, pages=[("doc_a", 1)]),
        _reference("q_gold_empty", answer_type=AnswerType.FREE_TEXT, pages=[]),
    ]
    submission = {
        "answers": [
            _answer(
                "q_raw_miss",
                raw=[_page_ref("doc_b", 2)],
                pass_a=[_page_ref("doc_b", 2)],
                final=[_page_ref("doc_b", 2)],
            ),
            _answer(
                "q_pass_a_miss",
                raw=[_page_ref("doc_a", 1)],
                pass_a=[_page_ref("doc_b", 2)],
                final=[_page_ref("doc_b", 2)],
            ),
            _answer(
                "q_final_miss",
                raw=[_page_ref("doc_a", 1)],
                pass_a=[_page_ref("doc_a", 1)],
                final=[_page_ref("doc_b", 2)],
            ),
            _answer(
                "q_hit",
                raw=[_page_ref("doc_a", 1)],
                pass_a=[_page_ref("doc_a", 1)],
                final=[_page_ref("doc_a", 1)],
            ),
            _answer(
                "q_gold_empty",
                raw=[_page_ref("doc_a", 1)],
                pass_a=[_page_ref("doc_a", 1)],
                final=[_page_ref("doc_a", 1)],
            ),
        ]
    }

    rows = build_grounding_ledger_rows(
        run_id="run-a",
        submission_payload=submission,
        references=references,
    )
    buckets = {row.question_id: row.failure_bucket for row in rows}
    assert buckets == {
        "q_raw_miss": "raw_miss",
        "q_pass_a_miss": "pass_a_miss",
        "q_final_miss": "final_miss",
        "q_hit": "hit",
        "q_gold_empty": "gold_empty",
    }


def test_build_grounding_summary_computes_rates_and_means() -> None:
    """Validate run-level summary metrics with `gold_empty` exclusion from miss-rate denominator."""

    rows = [
        GroundingLedgerRow(
            run_id="run-a",
            question_id="q1",
            answer_type="number",
            gold_pages="doc_a:1",
            raw_pages="doc_b:2",
            pass_a_pages="doc_b:2",
            final_pages="doc_b:2",
            raw_hit_pages="",
            pass_a_hit_pages="",
            final_hit_pages="",
            raw_miss_pages="doc_a:1",
            pass_a_miss_pages="doc_a:1",
            final_miss_pages="doc_a:1",
            raw_recall=0.0,
            pass_a_recall=0.0,
            final_precision=0.0,
            final_grounding=0.0,
            failure_bucket="raw_miss",
        ),
        GroundingLedgerRow(
            run_id="run-a",
            question_id="q2",
            answer_type="boolean",
            gold_pages="doc_a:1",
            raw_pages="doc_a:1",
            pass_a_pages="doc_b:2",
            final_pages="doc_b:2",
            raw_hit_pages="doc_a:1",
            pass_a_hit_pages="",
            final_hit_pages="",
            raw_miss_pages="",
            pass_a_miss_pages="doc_a:1",
            final_miss_pages="doc_a:1",
            raw_recall=1.0,
            pass_a_recall=0.0,
            final_precision=0.0,
            final_grounding=0.0,
            failure_bucket="pass_a_miss",
        ),
        GroundingLedgerRow(
            run_id="run-a",
            question_id="q3",
            answer_type="date",
            gold_pages="doc_a:1",
            raw_pages="doc_a:1",
            pass_a_pages="doc_a:1",
            final_pages="doc_b:2",
            raw_hit_pages="doc_a:1",
            pass_a_hit_pages="doc_a:1",
            final_hit_pages="",
            raw_miss_pages="",
            pass_a_miss_pages="",
            final_miss_pages="doc_a:1",
            raw_recall=1.0,
            pass_a_recall=1.0,
            final_precision=0.0,
            final_grounding=0.0,
            failure_bucket="final_miss",
        ),
        GroundingLedgerRow(
            run_id="run-a",
            question_id="q4",
            answer_type="name",
            gold_pages="doc_a:1",
            raw_pages="doc_a:1",
            pass_a_pages="doc_a:1",
            final_pages="doc_a:1",
            raw_hit_pages="doc_a:1",
            pass_a_hit_pages="doc_a:1",
            final_hit_pages="doc_a:1",
            raw_miss_pages="",
            pass_a_miss_pages="",
            final_miss_pages="",
            raw_recall=1.0,
            pass_a_recall=1.0,
            final_precision=1.0,
            final_grounding=1.0,
            failure_bucket="hit",
        ),
        GroundingLedgerRow(
            run_id="run-a",
            question_id="q5",
            answer_type="free_text",
            gold_pages="",
            raw_pages="doc_a:1",
            pass_a_pages="doc_a:1",
            final_pages="doc_a:1",
            raw_hit_pages="",
            pass_a_hit_pages="",
            final_hit_pages="",
            raw_miss_pages="",
            pass_a_miss_pages="",
            final_miss_pages="",
            raw_recall=1.0,
            pass_a_recall=1.0,
            final_precision=0.0,
            final_grounding=0.0,
            failure_bucket="gold_empty",
        ),
    ]

    summary = build_grounding_summary(run_id="run-a", rows=rows)
    assert summary.question_count == 5
    assert summary.gold_empty_count == 1
    assert summary.raw_miss_count == 1
    assert summary.pass_a_miss_count == 1
    assert summary.final_miss_count == 1
    assert summary.hit_count == 1
    assert summary.raw_miss_rate == 0.25
    assert summary.pass_a_miss_rate == 0.25
    assert summary.final_miss_rate == 0.25
    assert summary.mean_raw_recall == 0.75
    assert summary.mean_pass_a_recall == 0.5
    assert summary.mean_final_grounding == 0.25


def test_build_top_failures_from_ledger_dir_aggregates_across_runs(tmp_path: Path) -> None:
    """Ensure top failures are ranked by repeated failures across multiple run ledgers."""

    ledger_dir = tmp_path / "ledger"
    ledger_dir.mkdir(parents=True, exist_ok=True)
    write_grounding_ledger_csv(
        path=ledger_dir / "run-a.csv",
        rows=[
            GroundingLedgerRow(
                run_id="run-a",
                question_id="q_common",
                answer_type="free_text",
                gold_pages="doc_a:1",
                raw_pages="doc_b:2",
                pass_a_pages="doc_b:2",
                final_pages="doc_b:2",
                raw_hit_pages="",
                pass_a_hit_pages="",
                final_hit_pages="",
                raw_miss_pages="doc_a:1",
                pass_a_miss_pages="doc_a:1",
                final_miss_pages="doc_a:1",
                raw_recall=0.0,
                pass_a_recall=0.0,
                final_precision=0.0,
                final_grounding=0.0,
                failure_bucket="raw_miss",
            ),
            GroundingLedgerRow(
                run_id="run-a",
                question_id="q_hit",
                answer_type="number",
                gold_pages="doc_a:1",
                raw_pages="doc_a:1",
                pass_a_pages="doc_a:1",
                final_pages="doc_a:1",
                raw_hit_pages="doc_a:1",
                pass_a_hit_pages="doc_a:1",
                final_hit_pages="doc_a:1",
                raw_miss_pages="",
                pass_a_miss_pages="",
                final_miss_pages="",
                raw_recall=1.0,
                pass_a_recall=1.0,
                final_precision=1.0,
                final_grounding=1.0,
                failure_bucket="hit",
            ),
        ],
    )
    write_grounding_ledger_csv(
        path=ledger_dir / "run-b.csv",
        rows=[
            GroundingLedgerRow(
                run_id="run-b",
                question_id="q_common",
                answer_type="free_text",
                gold_pages="doc_a:1",
                raw_pages="doc_a:1",
                pass_a_pages="doc_a:1",
                final_pages="doc_b:2",
                raw_hit_pages="doc_a:1",
                pass_a_hit_pages="doc_a:1",
                final_hit_pages="",
                raw_miss_pages="",
                pass_a_miss_pages="",
                final_miss_pages="doc_a:1",
                raw_recall=1.0,
                pass_a_recall=1.0,
                final_precision=0.0,
                final_grounding=0.0,
                failure_bucket="final_miss",
            ),
            GroundingLedgerRow(
                run_id="run-b",
                question_id="q_once",
                answer_type="boolean",
                gold_pages="doc_a:1",
                raw_pages="doc_a:1",
                pass_a_pages="doc_b:2",
                final_pages="doc_b:2",
                raw_hit_pages="doc_a:1",
                pass_a_hit_pages="",
                final_hit_pages="",
                raw_miss_pages="",
                pass_a_miss_pages="doc_a:1",
                final_miss_pages="doc_a:1",
                raw_recall=1.0,
                pass_a_recall=0.0,
                final_precision=0.0,
                final_grounding=0.0,
                failure_bucket="pass_a_miss",
            ),
        ],
    )

    top_rows = build_top_failures_from_ledger_dir(ledger_dir=ledger_dir, top_n=10)
    assert top_rows
    assert top_rows[0]["question_id"] == "q_common"
    assert top_rows[0]["run_count"] == 2
    assert top_rows[0]["total_failures"] == 2
