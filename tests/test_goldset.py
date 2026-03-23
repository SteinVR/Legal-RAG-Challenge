from __future__ import annotations

from src.common.schemas import QuestionRecord
from src.evaluation.contracts import AnswerType, AssistantScoreRecord, PageReference, ReferenceAnswerRecord
from src.evaluation.goldset import (
    UNANSWERABLE_FREE_TEXT_ANSWER,
    GoldShardBundle,
    build_shard_manifest,
    collect_reviewed_assistant_scores,
    merge_reviewed_shards,
    split_questions_stratified,
)


def _question(question_id: str, answer_type: str, question: str) -> QuestionRecord:
    return QuestionRecord(id=question_id, answer_type=answer_type, question=question)


def test_split_questions_stratified_balances_and_preserves_uniqueness() -> None:
    questions = [
        _question("q01", "boolean", "Is there any overlap between case CA 001/2025 and case CFI 002/2025?"),
        _question("q02", "boolean", "Does Article 1 permit registration?"),
        _question("q03", "boolean", "Is there any overlap between case CA 003/2025 and case CFI 004/2025?"),
        _question("q04", "boolean", "Does Article 2 permit registration?"),
        _question("q05", "free_text", "Summarize the order for case CFI 005/2025."),
        _question("q06", "free_text", "What kind of liability applies under the statute?"),
        _question("q07", "free_text", "Summarize both cases CA 007/2025 and CFI 008/2025."),
        _question("q08", "free_text", "What does the title page say?"),
        _question("q09", "number", "What is the fine under Article 9?"),
        _question("q10", "number", "How many days are allowed under Article 10?"),
    ]

    shards = split_questions_stratified(questions, shard_count=5)
    manifest = build_shard_manifest(shards)

    assert len(shards) == 5
    assert all(len(shard.questions) == 2 for shard in shards)
    assert manifest.question_count == 10
    assert {question.id for shard in shards for question in shard.questions} == {q.id for q in questions}


def test_merge_reviewed_shards_returns_reference_only_dataset_by_default() -> None:
    questions = [
        _question("q1", "number", "How many days?"),
        _question("q2", "free_text", "Summarize the order."),
    ]
    reviewed_bundles = [
        GoldShardBundle(
            shard_id="part_01",
            status="reviewed",
            question_ids=["q1"],
            references=[
                ReferenceAnswerRecord(
                    question_id="q1",
                    question="How many days?",
                    answer_type=AnswerType.NUMBER,
                    answer=30,
                    gold_retrieval=[PageReference(doc_id="alpha", page_numbers=[1])],
                    tags=["deterministic", "single_page", "single_document"],
                )
            ],
        ),
        GoldShardBundle(
            shard_id="part_02",
            status="reviewed",
            question_ids=["q2"],
            references=[
                ReferenceAnswerRecord(
                    question_id="q2",
                    question="Summarize the order.",
                    answer_type=AnswerType.FREE_TEXT,
                    answer=UNANSWERABLE_FREE_TEXT_ANSWER,
                    gold_retrieval=[],
                    tags=["free_text", "negative", "single_document"],
                )
            ],
            assistant_scores=[AssistantScoreRecord(question_id="q2", assistant_score=1.0)],
        ),
    ]

    dataset = merge_reviewed_shards(
        reviewed_bundles=reviewed_bundles,
        questions=questions,
        benchmark_id="dev-gold",
    )

    assert dataset.benchmark_id == "dev-gold"
    assert [reference.question_id for reference in dataset.references] == ["q1", "q2"]
    assert dataset.assistant_scores == []

    assistant_scores = collect_reviewed_assistant_scores(
        reviewed_bundles=reviewed_bundles,
        questions=questions,
    )
    assert [score.question_id for score in assistant_scores] == ["q2"]


def test_merge_reviewed_shards_can_embed_assistant_scores_when_requested() -> None:
    questions = [_question("q1", "free_text", "Summarize the order.")]
    reviewed_bundles = [
        GoldShardBundle(
            shard_id="part_01",
            status="reviewed",
            question_ids=["q1"],
            references=[
                ReferenceAnswerRecord(
                    question_id="q1",
                    question="Summarize the order.",
                    answer_type=AnswerType.FREE_TEXT,
                    answer=UNANSWERABLE_FREE_TEXT_ANSWER,
                    gold_retrieval=[],
                    tags=["free_text", "negative", "single_document"],
                )
            ],
            assistant_scores=[AssistantScoreRecord(question_id="q1", assistant_score=1.0)],
        )
    ]

    dataset = merge_reviewed_shards(
        reviewed_bundles=reviewed_bundles,
        questions=questions,
        benchmark_id="dev-gold",
        include_assistant_scores=True,
    )

    assert [score.question_id for score in dataset.assistant_scores] == ["q1"]


def test_merge_reviewed_shards_rejects_missing_free_text_scores() -> None:
    questions = [_question("q1", "free_text", "Summarize the order.")]
    reviewed_bundles = [
        GoldShardBundle(
            shard_id="part_01",
            status="reviewed",
            question_ids=["q1"],
            references=[
                ReferenceAnswerRecord(
                    question_id="q1",
                    question="Summarize the order.",
                    answer_type=AnswerType.FREE_TEXT,
                    answer=UNANSWERABLE_FREE_TEXT_ANSWER,
                    gold_retrieval=[],
                    tags=["free_text", "negative", "single_document"],
                )
            ],
        )
    ]

    try:
        merge_reviewed_shards(
            reviewed_bundles=reviewed_bundles,
            questions=questions,
            benchmark_id="dev-gold",
        )
    except ValueError as exc:
        assert "assistant_scores" in str(exc)
    else:
        raise AssertionError("Expected merge_reviewed_shards to fail without assistant_scores.")
