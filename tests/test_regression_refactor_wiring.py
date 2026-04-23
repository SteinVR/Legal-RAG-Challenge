"""Regression tests for refactor wiring failures that caused runtime NameError."""

from __future__ import annotations

from pathlib import Path

from src.answering import service_helpers as answering_helpers
from src.answering.service_types import _PageCandidate
from src.common.schemas import QuestionRecord
from src.evaluation.contracts import AnswerType, PageReference, ReferenceAnswerRecord
from src.evaluation.goldset_core import (
    GoldShardBundle,
    merge_reviewed_shards,
    sample_questions_stratified,
    split_questions_stratified,
)
from src.main_handlers import _resolve_assistant_scores_path


def _question(*, question_id: str, text: str, answer_type: str) -> QuestionRecord:
    """Build a compact question fixture for goldset helper tests."""

    return QuestionRecord(id=question_id, question=text, answer_type=answer_type)


def test_goldset_split_questions_stratified_runtime_wiring() -> None:
    """Ensure stratified split executes without missing helper symbol wiring."""

    questions = [
        _question(question_id="q1", text="How many days are allowed?", answer_type="number"),
        _question(question_id="q2", text="Is prior notice required?", answer_type="boolean"),
    ]

    shards = split_questions_stratified(questions, shard_count=2)

    assert len(shards) == 2
    flattened_ids = [question.id for shard in shards for question in shard.questions]
    assert set(flattened_ids) == {"q1", "q2"}
    assert all(len(shard.questions) == 1 for shard in shards)


def test_goldset_sample_questions_stratified_runtime_wiring() -> None:
    """Ensure stratified sampling executes without missing helper symbol wiring."""

    questions = [
        _question(question_id="q1", text="How many days are allowed?", answer_type="number"),
        _question(question_id="q2", text="Is prior notice required?", answer_type="boolean"),
        _question(question_id="q3", text="State the court's rationale.", answer_type="free_text"),
        _question(question_id="q4", text="When was the order issued?", answer_type="date"),
    ]

    sampled = sample_questions_stratified(questions, sample_count=2)

    assert len(sampled) == 2
    assert len({question.id for question in sampled}) == 2
    assert {question.id for question in sampled}.issubset({question.id for question in questions})


def test_goldset_merge_reviewed_shards_runtime_wiring() -> None:
    """Ensure reviewed shard merge executes without missing helper symbol wiring."""

    questions = [_question(question_id="q1", text="How many days are allowed?", answer_type="number")]
    bundle = GoldShardBundle(
        shard_id="part_01",
        status="reviewed",
        question_ids=["q1"],
        references=[
            ReferenceAnswerRecord(
                question_id="q1",
                answer_type=AnswerType.NUMBER,
                answer=30,
                question=questions[0].question,
                gold_retrieval=[PageReference(doc_id="doc_1", page_numbers=[1])],
            )
        ],
        assistant_scores=[],
    )

    dataset = merge_reviewed_shards(
        reviewed_bundles=[bundle],
        questions=questions,
        benchmark_id="benchmark-regression",
        include_assistant_scores=True,
    )

    assert len(dataset.references) == 1
    assert dataset.references[0].question_id == "q1"
    assert dataset.assistant_scores == []


def test_free_text_subset_pair_search_runtime_wiring(monkeypatch) -> None:
    """Ensure free-text subset search can iterate subsets without NameError crashes."""

    pages = [
        _PageCandidate(doc_id="doc_a", page_numbers=(1,), text="Alpha clause text.", include_page_numbers=False),
        _PageCandidate(doc_id="doc_a", page_numbers=(2,), text="Beta clause text.", include_page_numbers=False),
    ]

    def _supported_only_single_page(*, answer: str, pages: object) -> bool:
        """Force subset branch: reject full set, accept single-page subsets."""

        del answer
        return len(list(pages)) == 1

    monkeypatch.setattr(answering_helpers, "_is_free_text_answer_supported", _supported_only_single_page)

    supported_pairs = answering_helpers._supported_page_pairs_for_free_text(
        answer="Synthetic free-text response.",
        pages=pages,
    )

    assert supported_pairs == {("doc_a", 1)}


def test_benchmark_assistant_score_path_auto_resolution(tmp_path: Path) -> None:
    """Ensure benchmark summary can auto-resolve adjacent assistant scores artifact."""

    benchmark_path = tmp_path / "dev-gold-warmup100-v1.benchmark.json"
    assistant_scores_path = tmp_path / "dev-gold-warmup100-v1.assistant_scores.json"
    benchmark_path.write_text("{}", encoding="utf-8")
    assistant_scores_path.write_text("[]", encoding="utf-8")

    resolved = _resolve_assistant_scores_path(
        raw_assistant_scores_path=None,
        benchmark_path=str(benchmark_path),
    )
    assert resolved == assistant_scores_path

    explicit = _resolve_assistant_scores_path(
        raw_assistant_scores_path=str(assistant_scores_path),
        benchmark_path=str(benchmark_path),
    )
    assert explicit == assistant_scores_path
