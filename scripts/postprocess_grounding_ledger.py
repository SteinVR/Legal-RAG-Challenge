#!/usr/bin/env python3
"""Build recall-first grounding ledger artifacts from submission telemetry."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.evaluation.contracts import load_reference_records, load_submission_payload
from src.evaluation.grounding_ledger import (
    build_grounding_ledger_rows,
    build_grounding_summary,
    build_grounding_summary_payload,
    build_top_failures_from_runs_dir,
    upsert_summary_row,
    write_grounding_ledger_csv,
    write_grounding_ledger_jsonl,
    write_top_failures_tsv,
)


def _write_manifest(
    *,
    run_id: str,
    run_dir: Path,
    warmup_root: Path,
    submission_path: Path,
    benchmark_path: Path,
    summary_json_path: Path,
    ledger_jsonl_path: Path,
    ledger_csv_path: Path,
    summary_runs_tsv_path: Path,
    top_failures_tsv_path: Path,
    grounding_summary: dict[str, object],
) -> None:
    """Write a minimal manifest for grounding-only bundles."""

    manifest_path = run_dir / "manifest.json"
    payload = {
        "run_id": run_id,
        "phase": "warmup",
        "run_kind": "grounding_only",
        "artifacts": {
            "warmup_root": str(warmup_root.resolve()),
            "submission_dir": str((run_dir / "submission").resolve()) if (run_dir / "submission").exists() else None,
            "eval_dir": str((run_dir / "eval").resolve()) if (run_dir / "eval").exists() else None,
            "grounding_dir": str((run_dir / "grounding").resolve()),
            "submission_json": str(submission_path.resolve()),
            "benchmark_path": str(benchmark_path.resolve()),
            "grounding_summary_json": str(summary_json_path.resolve()),
            "grounding_ledger_jsonl": str(ledger_jsonl_path.resolve()),
            "grounding_ledger_csv": str(ledger_csv_path.resolve()),
            "summary_runs_tsv": str(summary_runs_tsv_path.resolve()),
            "top_failures_tsv": str(top_failures_tsv_path.resolve()),
        },
        "benchmark": None,
        "grounding": grounding_summary,
    }
    manifest_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def _build_parser() -> argparse.ArgumentParser:
    """Build command-line parser for grounding ledger post-processing."""

    parser = argparse.ArgumentParser(description="Generate grounding ledger and summaries from submission telemetry.")
    parser.add_argument("--run-id", required=True, help="Experiment/run identifier.")
    parser.add_argument("--submission-path", required=True, help="Path to submission.json.")
    parser.add_argument("--benchmark-path", required=True, help="Path to benchmark JSON/JSONL references.")
    parser.add_argument(
        "--run-dir",
        help="Optional run bundle directory. Defaults to artifacts/warmup_runs/runs/<run-id>.",
    )
    parser.add_argument(
        "--warmup-root",
        default="artifacts/warmup_runs",
        help="Root directory for structured warmup run artifacts.",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=20,
        help="Number of top persistent failure question_ids to keep.",
    )
    return parser


def main() -> int:
    """Execute grounding-ledger post-processing and write run artifacts."""

    args = _build_parser().parse_args()
    run_id = str(args.run_id).strip()
    if not run_id:
        raise ValueError("--run-id must be a non-empty string.")

    submission_payload = load_submission_payload(args.submission_path)
    references = load_reference_records(args.benchmark_path)
    rows = build_grounding_ledger_rows(
        run_id=run_id,
        submission_payload=submission_payload,
        references=references,
    )
    summary = build_grounding_summary(run_id=run_id, rows=rows)

    warmup_root = Path(args.warmup_root)
    run_dir = Path(args.run_dir) if args.run_dir else warmup_root / "runs" / run_id
    grounding_dir = run_dir / "grounding"
    runs_dir = warmup_root / "runs"
    ledger_jsonl_path = grounding_dir / "ledger.jsonl"
    ledger_csv_path = grounding_dir / "ledger.csv"
    summary_path = warmup_root / "summary_runs.tsv"
    top_failures_path = warmup_root / "top_failures.tsv"
    summary_json_path = grounding_dir / "summary.json"

    write_grounding_ledger_jsonl(path=ledger_jsonl_path, rows=rows)
    write_grounding_ledger_csv(path=ledger_csv_path, rows=rows)
    upsert_summary_row(path=summary_path, summary=summary)
    top_failures = build_top_failures_from_runs_dir(
        runs_dir=runs_dir,
        top_n=max(int(args.top_n), 0),
    )
    write_top_failures_tsv(path=top_failures_path, rows=top_failures)

    summary_json_path.parent.mkdir(parents=True, exist_ok=True)
    summary_payload = build_grounding_summary_payload(
        summary=summary,
        rows=rows,
        ledger_jsonl_path=ledger_jsonl_path,
        ledger_csv_path=ledger_csv_path,
        summary_runs_tsv_path=summary_path,
        top_failures_tsv_path=top_failures_path,
    )
    summary_json_path.write_text(json.dumps(summary_payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    _write_manifest(
        run_id=run_id,
        run_dir=run_dir,
        warmup_root=warmup_root,
        submission_path=Path(args.submission_path),
        benchmark_path=Path(args.benchmark_path),
        summary_json_path=summary_json_path,
        ledger_jsonl_path=ledger_jsonl_path,
        ledger_csv_path=ledger_csv_path,
        summary_runs_tsv_path=summary_path,
        top_failures_tsv_path=top_failures_path,
        grounding_summary=summary_payload,
    )

    print(f"run_id={run_id}")
    print(f"question_count={summary.question_count}")
    print(f"raw_miss_rate={summary.raw_miss_rate:.12f}")
    print(f"pass_a_miss_rate={summary.pass_a_miss_rate:.12f}")
    print(f"final_miss_rate={summary.final_miss_rate:.12f}")
    print(f"mean_raw_recall={summary.mean_raw_recall:.12f}")
    print(f"mean_pass_a_recall={summary.mean_pass_a_recall:.12f}")
    print(f"mean_final_grounding={summary.mean_final_grounding:.12f}")
    print(f"ledger_jsonl={ledger_jsonl_path}")
    print(f"ledger_csv={ledger_csv_path}")
    print(f"summary_runs_tsv={summary_path}")
    print(f"top_failures_tsv={top_failures_path}")
    print(f"summary_json={summary_json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
