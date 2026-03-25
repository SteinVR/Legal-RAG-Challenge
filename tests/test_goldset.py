from __future__ import annotations

from src.evaluation.contracts import AnswerType, AssistantScoreRecord, PageReference, ReferenceAnswerRecord
from src.evaluation.dev_benchmark import BenchmarkDataset
from src.evaluation.goldset import (
    UNANSWERABLE_FREE_TEXT_ANSWER,
    GoldShardBundle,
    build_shard_manifest,
    collect_referenced_doc_ids,
    collect_reviewed_assistant_scores,
    combine_assistant_score_sets,
    combine_benchmark_datasets,
    combine_question_sets,
    merge_reviewed_shards,
    sample_questions_stratified,
    split_questions_stratified,
)
from tests.support.answering import question_record as _question


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


def test_sample_questions_stratified_is_deterministic_and_covers_rare_strata() -> None:
    questions = [
        _question("q01", "boolean", "Is there any overlap between case CA 001/2025 and case CFI 002/2025?"),
        _question("q02", "boolean", "Is there any overlap between case CA 003/2025 and case CFI 004/2025?"),
        _question("q03", "boolean", "Does Article 1 apply?"),
        _question("q04", "boolean", "Does Article 2 apply?"),
        _question("q05", "free_text", "Summarize the order in case CFI 005/2025."),
        _question("q06", "free_text", "Summarize the order in case CFI 006/2025."),
        _question("q07", "free_text", "Is there any information about plea bargaining in case CFI 007/2025?"),
        _question("q08", "free_text", "Is there any information about parole hearings in case CFI 008/2025?"),
        _question("q09", "number", "How many days are allowed under Article 9?"),
        _question("q10", "number", "How many days are allowed under Article 10?"),
        _question("q11", "name", "Which case between CA 011/2025 and CFI 012/2025 was issued earlier?"),
        _question("q12", "date", "What is the date of issue for case SCT 013/2025?"),
    ]

    sampled_once = sample_questions_stratified(questions, sample_count=7)
    sampled_twice = sample_questions_stratified(questions, sample_count=7)

    assert [question.id for question in sampled_once] == [question.id for question in sampled_twice]
    assert len(sampled_once) == 7
    assert {question.id for question in sampled_once} == {question.id for question in sampled_twice}
    assert any(question.id in {"q07", "q08"} for question in sampled_once)
    assert any(question.id in {"q01", "q02", "q11"} for question in sampled_once)


def test_combine_gold_question_benchmark_and_score_sets() -> None:
    warmup_questions = [
        _question("q1", "number", "How many days?"),
        _question("q2", "free_text", "Summarize the order."),
    ]
    full_questions = [_question("q3", "free_text", "Who administers the law?")]

    warmup_benchmark = BenchmarkDataset(
        benchmark_id="warmup",
        references=[
            ReferenceAnswerRecord(
                question_id="q1",
                question="How many days?",
                answer_type=AnswerType.NUMBER,
                answer=30,
                gold_retrieval=[PageReference(doc_id="alpha", page_numbers=[1])],
                tags=["deterministic", "single_page", "single_document"],
            ),
            ReferenceAnswerRecord(
                question_id="q2",
                question="Summarize the order.",
                answer_type=AnswerType.FREE_TEXT,
                answer=UNANSWERABLE_FREE_TEXT_ANSWER,
                gold_retrieval=[],
                tags=["free_text", "negative", "single_document"],
            ),
        ],
    )
    full_benchmark = BenchmarkDataset(
        benchmark_id="full50",
        references=[
            ReferenceAnswerRecord(
                question_id="q3",
                question="Who administers the law?",
                answer_type=AnswerType.FREE_TEXT,
                answer="The Registrar administers the law.",
                gold_retrieval=[PageReference(doc_id="beta", page_numbers=[2])],
                tags=["free_text", "single_page", "single_document"],
            )
        ],
    )

    combined_questions = combine_question_sets([warmup_questions, full_questions])
    combined_benchmark = combine_benchmark_datasets(
        questions=combined_questions,
        benchmarks=[warmup_benchmark, full_benchmark],
        benchmark_id="dev-gold-150",
    )
    combined_scores = combine_assistant_score_sets(
        questions=combined_questions,
        assistant_score_sets=[
            [AssistantScoreRecord(question_id="q2", assistant_score=1.0)],
            [AssistantScoreRecord(question_id="q3", assistant_score=0.9)],
        ],
    )

    assert [question.id for question in combined_questions] == ["q1", "q2", "q3"]
    assert [reference.question_id for reference in combined_benchmark.references] == ["q1", "q2", "q3"]
    assert combined_benchmark.assistant_scores == []
    assert [score.question_id for score in combined_scores] == ["q2", "q3"]
    assert collect_referenced_doc_ids(combined_benchmark.references) == ["alpha", "beta"]
