#!/usr/bin/env python3
"""Prepare and merge gold-set shard artifacts."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from src.evaluation.contracts import load_assistant_score_records
from src.evaluation.dev_benchmark import load_benchmark_dataset
from src.evaluation.goldset import (
    build_question_set_summary,
    build_shard_manifest,
    build_shard_scaffold,
    collect_referenced_doc_ids,
    collect_reviewed_assistant_scores,
    combine_assistant_score_sets,
    combine_benchmark_datasets,
    combine_question_sets,
    load_gold_shard_bundle,
    load_questions,
    merge_reviewed_shards,
    sample_questions_stratified,
    split_questions_stratified,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    sample_parser = subparsers.add_parser(
        "sample",
        help="Select a deterministic stratified subset of questions and write a sample manifest.",
    )
    sample_parser.add_argument("--questions-path", required=True, help="Path to the source questions JSON.")
    sample_parser.add_argument("--output-dir", required=True, help="Directory where sample artifacts will be written.")
    sample_parser.add_argument("--sample-count", type=int, required=True, help="Number of questions to sample.")

    split_parser = subparsers.add_parser("split", help="Split a question file into deterministic stratified shards.")
    split_parser.add_argument("--questions-path", required=True, help="Path to the source questions JSON.")
    split_parser.add_argument("--output-dir", required=True, help="Directory where shard artifacts will be written.")
    split_parser.add_argument("--shard-count", type=int, default=5, help="Number of shards to create.")

    merge_parser = subparsers.add_parser(
        "merge", help="Merge reviewed shard bundles into a benchmark dataset."
    )
    merge_parser.add_argument("--questions-path", required=True, help="Path to the source questions JSON.")
    merge_parser.add_argument("--review-dir", required=True, help="Directory containing reviewed shard bundles.")
    merge_parser.add_argument("--output-path", required=True, help="Path to write the merged benchmark dataset.")
    merge_parser.add_argument("--benchmark-id", required=True, help="BenchmarkDataset.benchmark_id value.")
    merge_parser.add_argument("--title", help="Optional BenchmarkDataset.title override.")
    merge_parser.add_argument(
        "--assistant-scores-output-path",
        help="Optional path to write reviewed free-text assistant_scores as a separate JSON file.",
    )
    merge_parser.add_argument(
        "--embed-assistant-scores",
        action="store_true",
        help="Embed reviewed assistant_scores into the merged benchmark dataset.",
    )

    assemble_parser = subparsers.add_parser(
        "assemble",
        help="Assemble a combined consumer-ready gold dataset from question, benchmark, score, and document sources.",
    )
    assemble_parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory where the assembled dataset will be written.",
    )
    assemble_parser.add_argument(
        "--questions-path",
        dest="questions_paths",
        action="append",
        required=True,
        help="Question file to include. Pass multiple times in the desired combined order.",
    )
    assemble_parser.add_argument(
        "--benchmark-path",
        dest="benchmark_paths",
        action="append",
        required=True,
        help="Reference-only benchmark dataset to include. Pass multiple times.",
    )
    assemble_parser.add_argument(
        "--assistant-scores-path",
        dest="assistant_scores_paths",
        action="append",
        required=True,
        help="Assistant score file to include. Pass multiple times.",
    )
    assemble_parser.add_argument(
        "--documents-dir",
        dest="documents_dirs",
        action="append",
        required=True,
        help="Document directory to search when copying referenced PDFs. Pass multiple times.",
    )
    assemble_parser.add_argument("--benchmark-id", required=True, help="BenchmarkDataset.benchmark_id value.")
    assemble_parser.add_argument("--title", help="Optional BenchmarkDataset.title override.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "sample":
        return _run_sample(args)
    if args.command == "split":
        return _run_split(args)
    if args.command == "merge":
        return _run_merge(args)
    if args.command == "assemble":
        return _run_assemble(args)
    raise ValueError(f"Unsupported command: {args.command}")


def _run_sample(args: argparse.Namespace) -> int:
    questions = load_questions(args.questions_path)
    sampled_questions = sample_questions_stratified(questions, sample_count=args.sample_count)
    summary = build_question_set_summary(sampled_questions)
    output_dir = Path(args.output_dir)

    write_json(
        output_dir / "sampled.questions.json",
        [question.model_dump(mode="json") for question in sampled_questions],
    )
    write_json(
        output_dir / "sample_manifest.json",
        {
            "source_question_count": len(questions),
            "sample": summary.model_dump(mode="json"),
        },
    )
    print(json.dumps(summary.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 0


def _run_split(args: argparse.Namespace) -> int:
    questions = load_questions(args.questions_path)
    shards = split_questions_stratified(questions, shard_count=args.shard_count)
    manifest = build_shard_manifest(shards)
    output_dir = Path(args.output_dir)

    for shard in shards:
        shard_payload = [question.model_dump(mode="json") for question in shard.questions]
        write_json(output_dir / "shards" / f"{shard.shard_id}.questions.json", shard_payload)
        write_json(
            output_dir / "drafts" / f"{shard.shard_id}.bundle.json",
            build_shard_scaffold(shard, status="draft").model_dump(mode="json"),
        )
        write_json(
            output_dir / "reviews" / f"{shard.shard_id}.bundle.json",
            build_shard_scaffold(shard, status="reviewed").model_dump(mode="json"),
        )

    write_json(output_dir / "shard_manifest.json", manifest.model_dump(mode="json"))
    print(json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 0


def _run_merge(args: argparse.Namespace) -> int:
    questions = load_questions(args.questions_path)
    review_dir = Path(args.review_dir)
    review_paths = sorted(review_dir.glob("*.bundle.json"))
    bundles = [load_gold_shard_bundle(path) for path in review_paths]
    dataset = merge_reviewed_shards(
        reviewed_bundles=bundles,
        questions=questions,
        benchmark_id=args.benchmark_id,
        title=args.title,
        include_assistant_scores=args.embed_assistant_scores,
    )
    write_json(Path(args.output_path), dataset.model_dump(mode="json"))
    if args.assistant_scores_output_path:
        assistant_scores = collect_reviewed_assistant_scores(
            reviewed_bundles=bundles,
            questions=questions,
        )
        write_json(
            Path(args.assistant_scores_output_path),
            [score.model_dump(mode="json") for score in assistant_scores],
        )
    print(json.dumps(dataset.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 0


def _run_assemble(args: argparse.Namespace) -> int:
    question_sets = [load_questions(path) for path in args.questions_paths]
    benchmark_datasets = [load_benchmark_dataset(path) for path in args.benchmark_paths]
    assistant_score_sets = [load_assistant_score_records(path) for path in args.assistant_scores_paths]
    combined_questions = combine_question_sets(question_sets)
    combined_dataset = combine_benchmark_datasets(
        questions=combined_questions,
        benchmarks=benchmark_datasets,
        benchmark_id=args.benchmark_id,
        title=args.title,
    )
    combined_assistant_scores = combine_assistant_score_sets(
        questions=combined_questions,
        assistant_score_sets=assistant_score_sets,
    )
    output_dir = Path(args.output_dir)
    question_summary = build_question_set_summary(combined_questions)
    copied_docs = _copy_referenced_documents(
        doc_ids=collect_referenced_doc_ids(combined_dataset.references),
        source_dirs=[Path(path) for path in args.documents_dirs],
        target_dir=output_dir / "documents" / "pdfs",
    )

    write_json(
        output_dir / "questions" / "questions.json",
        [question.model_dump(mode="json") for question in combined_questions],
    )
    write_json(output_dir / f"{args.benchmark_id}.benchmark.json", combined_dataset.model_dump(mode="json"))
    write_json(
        output_dir / f"{args.benchmark_id}.assistant_scores.json",
        [score.model_dump(mode="json") for score in combined_assistant_scores],
    )
    write_json(
        output_dir / "assembly_manifest.json",
        {
            "benchmark_id": args.benchmark_id,
            "title": combined_dataset.title,
            "question_summary": question_summary.model_dump(mode="json"),
            "reference_count": len(combined_dataset.references),
            "assistant_score_count": len(combined_assistant_scores),
            "document_count": len(copied_docs),
            "document_ids": copied_docs,
            "inputs": {
                "questions_paths": list(args.questions_paths),
                "benchmark_paths": list(args.benchmark_paths),
                "assistant_scores_paths": list(args.assistant_scores_paths),
                "documents_dirs": list(args.documents_dirs),
            },
        },
    )
    print(
        json.dumps(
            {
                "question_count": len(combined_questions),
                "reference_count": len(combined_dataset.references),
                "assistant_score_count": len(combined_assistant_scores),
                "document_count": len(copied_docs),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _copy_referenced_documents(*, doc_ids: list[str], source_dirs: list[Path], target_dir: Path) -> list[str]:
    target_dir.mkdir(parents=True, exist_ok=True)
    for stale_pdf_path in target_dir.glob("*.pdf"):
        stale_pdf_path.unlink()

    copied_doc_ids: list[str] = []
    for doc_id in doc_ids:
        filename = f"{doc_id}.pdf"
        source_path = _resolve_source_document_path(filename=filename, source_dirs=source_dirs)
        if source_path is None:
            raise ValueError(f"Could not find referenced document {filename} in any provided --documents-dir.")
        shutil.copy2(source_path, target_dir / filename)
        copied_doc_ids.append(doc_id)
    return copied_doc_ids


def _resolve_source_document_path(*, filename: str, source_dirs: list[Path]) -> Path | None:
    for source_dir in source_dirs:
        candidate = source_dir / filename
        if candidate.exists():
            return candidate
    return None


if __name__ == "__main__":
    raise SystemExit(main())
