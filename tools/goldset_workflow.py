#!/usr/bin/env python3
"""Prepare and merge gold-set shard artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.evaluation.goldset import (
    build_shard_manifest,
    build_shard_scaffold,
    collect_reviewed_assistant_scores,
    load_gold_shard_bundle,
    load_questions,
    merge_reviewed_shards,
    split_questions_stratified,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "split":
        return _run_split(args)
    if args.command == "merge":
        return _run_merge(args)
    raise ValueError(f"Unsupported command: {args.command}")


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


if __name__ == "__main__":
    raise SystemExit(main())
