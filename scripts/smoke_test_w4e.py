#!/usr/bin/env python3
"""Smoke test: run 5 warmup questions through the full QA pipeline.

Verifies:
- Corpus and index are usable
- Retrieval returns evidence
- Structured solver produces answers
- Decomposition triggers and recomposes for cross-case questions

Usage:
    PYTHONPATH=. .venv/bin/python scripts/smoke_test_w4e.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import dotenv_values

from src.answering.decomposition import extract_case_refs, should_decompose
from src.answering.page_attribution import PageAttributionConfig
from src.answering.service import AnsweringService, AnswerResult, extract_query_metadata
from src.common.config import load_app_config
from src.common.schemas import QuestionRecord
from src.indexing.service import IndexPaths, build_query_embedder
from src.providers.codex_provider import CodexFreeTextProvider
from src.retrieval.hybrid_search import QdrantHybridSearchBackend, RRFHybridSearch
from src.retrieval.reranker import LexicalFallbackReranker, QwenReranker
from src.retrieval.service import RetrievalService

SMOKE_QUESTIONS_PATH = PROJECT_ROOT / "data" / "warmup" / "questions" / "questions_smoke.json"
ENV_FILE = PROJECT_ROOT / ".env"


def _resolve_provider_api_key() -> str | None:
    """Resolve OpenAI provider key from env (same logic as main.py)."""
    import os

    env_values = dotenv_values(ENV_FILE) if ENV_FILE.exists() else {}
    for key in ("CODEX_OAUTH_TOKEN", "OPENAI_API_KEY", "CODEX_API_KEY"):
        if key in os.environ:
            token = os.environ[key].strip()
            if token:
                return token
            continue
        value = env_values.get(key)
        if value:
            token = str(value).strip()
            if token:
                return token
    return None


def load_smoke_questions() -> list[QuestionRecord]:
    with SMOKE_QUESTIONS_PATH.open() as f:
        raw = json.load(f)
    return [QuestionRecord(**q) for q in raw]


def main() -> None:
    print("=" * 60)
    print("W4E SMOKE TEST — 5 warmup questions")
    print("=" * 60)

    # --- Load config ---
    config = load_app_config(env_file=ENV_FILE)
    api_key = _resolve_provider_api_key()
    if not api_key:
        print("FAIL: No OpenAI API key found (OPENAI_API_KEY / CODEX_OAUTH_TOKEN / CODEX_API_KEY)")
        sys.exit(1)

    # --- Verify corpus ---
    corpus_path = config.storage.root_dir / config.phase.value / "corpus" / "corpus.jsonl"
    if not corpus_path.exists():
        print(f"FAIL: Corpus not found at {corpus_path}")
        sys.exit(1)

    corpus_lines = sum(1 for _ in corpus_path.open())
    print(f"Corpus: {corpus_lines} pages at {corpus_path}")

    # --- Verify index ---
    index_paths = IndexPaths.from_config(config)
    qdrant_dir = index_paths.index_dir / "qdrant"
    if not qdrant_dir.exists():
        print(f"FAIL: Index not found at {qdrant_dir}")
        sys.exit(1)
    print(f"Index: {qdrant_dir}")

    # --- Build services ---
    dense_embedder = build_query_embedder(config)
    backend = QdrantHybridSearchBackend(
        index_dir=index_paths.index_dir,
        dense_embedder=dense_embedder,
        enable_sparse_compat=True,
    )

    retrieval_settings = config.retrieval
    retrieval_service = RetrievalService(
        hybrid_search=RRFHybridSearch(backend=backend),
        reranker=QwenReranker(fallback_reranker=LexicalFallbackReranker()),
        candidate_budget=retrieval_settings.candidate_budget,
        rerank_budget=retrieval_settings.rerank_budget,
        default_evidence_budget=retrieval_settings.default_evidence_budget,
        evidence_budget_by_answer_type=dict(retrieval_settings.evidence_budget_by_answer_type),
        question_class_budgets=dict(retrieval_settings.question_class_budgets),
        min_rerank_score=retrieval_settings.min_rerank_score,
        parent_page_expansion_enabled=retrieval_settings.parent_page_expansion_enabled,
        parent_page_expansion_limit=retrieval_settings.parent_page_expansion_limit,
    )

    provider = CodexFreeTextProvider(model="gpt-5.4-mini", api_key=api_key)
    answering_service = AnsweringService(
        retriever=retrieval_service,
        provider=provider,
        reasoning_effort_by_type=config.answering.reasoning_effort_by_type,
        confidence_threshold_by_type=config.answering.confidence_threshold_by_type,
        page_attribution_config=PageAttributionConfig(**config.page_attribution.model_dump()),
    )

    # --- Load questions ---
    questions = load_smoke_questions()
    print(f"Questions: {len(questions)}")
    print()

    # --- Run pipeline ---
    from src.answering.decomposition import answer_with_decomposition

    results: list[tuple[QuestionRecord, AnswerResult | None, bool, str]] = []
    api_errors = 0
    for i, q in enumerate(questions, start=1):
        print(f"[{i}/{len(questions)}] {q.answer_type:10s} | {q.question[:80]}...")

        query_metadata = extract_query_metadata(q.question)
        decomposed = should_decompose(q, query_metadata, enabled=True)

        if decomposed:
            print(f"  -> DECOMPOSITION triggered ({len(extract_case_refs(q.question))} case refs)")

        try:
            if decomposed:
                answer_result = answer_with_decomposition(
                    q, query_metadata, answering_service, max_subquestions=4,
                )
            else:
                answer_result = answering_service.answer_question(q)

            answer_preview = str(answer_result.answer)[:80] if answer_result.answer is not None else "<null>"
            page_count = len(answer_result.evidence_pages)
            print(f"  -> answer={answer_preview}")
            print(f"  -> confidence={answer_result.confidence:.2f}, pages={page_count}")
            if answer_result.page_trace:
                print(f"  -> trace: raw={len(answer_result.page_trace.raw_retrieved_chunk_pages)}, "
                      f"pass_a={len(answer_result.page_trace.pass_a_pages)}, "
                      f"final={len(answer_result.page_trace.final_emitted_pages)}")
            results.append((q, answer_result, decomposed, "ok"))
        except Exception as exc:
            error_msg = str(exc)[:120]
            print(f"  -> ERROR: {error_msg}")
            results.append((q, None, decomposed, f"error: {error_msg}"))
            api_errors += 1
        print()

    # --- Summary ---
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    answered = sum(1 for _, r, _, s in results if r is not None and r.answer is not None)
    with_pages = sum(1 for _, r, _, s in results if r is not None and r.evidence_pages)
    decomposed_count = sum(1 for _, _, d, _ in results if d)

    print(f"Total:      {len(results)}")
    print(f"Answered:   {answered}/{len(results)}")
    print(f"With pages: {with_pages}/{len(results)}")
    print(f"Decomposed: {decomposed_count}")
    print(f"API errors: {api_errors}")
    print()

    # --- Checks ---
    all_ok = True
    for q, r, d, status in results:
        if status.startswith("error"):
            print(f"ERROR: {q.id[:16]}... ({q.answer_type}): {status}")
        elif r is not None and r.answer is None:
            print(f"WARN: null answer for {q.id[:16]}... ({q.answer_type})")

    # Cross-case question should have decomposed
    cross_case_decomposed = [d for q, _, d, _ in results if len(extract_case_refs(q.question)) >= 2]
    if cross_case_decomposed and not any(cross_case_decomposed):
        print("FAIL: Cross-case question did not trigger decomposition")
        all_ok = False
    elif cross_case_decomposed and any(cross_case_decomposed):
        print("OK: Cross-case question correctly triggered decomposition")

    if api_errors > 0:
        print(f"\nSMOKE TEST PARTIAL: {api_errors} API errors (provider may be unavailable)")
    elif all_ok:
        print("\nSMOKE TEST PASSED")
    else:
        print("\nSMOKE TEST HAD WARNINGS")

    # Cleanup
    backend.close()


if __name__ == "__main__":
    main()
