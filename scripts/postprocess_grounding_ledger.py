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
    build_top_failures_from_ledger_dir,
    upsert_summary_row,
    write_grounding_ledger_csv,
    write_grounding_ledger_jsonl,
    write_top_failures_tsv,
)


def _build_parser() -> argparse.ArgumentParser:
    """Build command-line parser for grounding ledger post-processing."""

    parser = argparse.ArgumentParser(description="Generate grounding ledger and summaries from submission telemetry.")
    parser.add_argument("--run-id", required=True, help="Experiment/run identifier.")
    parser.add_argument("--submission-path", required=True, help="Path to submission.json.")
    parser.add_argument("--benchmark-path", required=True, help="Path to benchmark JSON/JSONL references.")
    parser.add_argument(
        "--ledger-dir",
        default="artifacts/autoresearch/ledger",
        help="Directory where per-run JSONL/CSV ledgers are written.",
    )
    parser.add_argument(
        "--analysis-dir",
        default="analysis/grounding",
        help="Directory where tracked summaries are written.",
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

    ledger_dir = Path(args.ledger_dir)
    analysis_dir = Path(args.analysis_dir)
    ledger_jsonl_path = ledger_dir / f"{run_id}.jsonl"
    ledger_csv_path = ledger_dir / f"{run_id}.csv"
    summary_path = analysis_dir / "summary_runs.tsv"
    top_failures_path = analysis_dir / "top_failures.tsv"
    summary_json_path = analysis_dir / f"{run_id}.summary.json"

    write_grounding_ledger_jsonl(path=ledger_jsonl_path, rows=rows)
    write_grounding_ledger_csv(path=ledger_csv_path, rows=rows)
    upsert_summary_row(path=summary_path, summary=summary)
    top_failures = build_top_failures_from_ledger_dir(ledger_dir=ledger_dir, top_n=max(int(args.top_n), 0))
    write_top_failures_tsv(path=top_failures_path, rows=top_failures)

    summary_json_path.parent.mkdir(parents=True, exist_ok=True)
    summary_json_path.write_text(
        json.dumps(
            {
                "run_id": summary.run_id,
                "question_count": summary.question_count,
                "gold_empty_count": summary.gold_empty_count,
                "raw_miss_count": summary.raw_miss_count,
                "pass_a_miss_count": summary.pass_a_miss_count,
                "final_miss_count": summary.final_miss_count,
                "hit_count": summary.hit_count,
                "raw_miss_rate": summary.raw_miss_rate,
                "pass_a_miss_rate": summary.pass_a_miss_rate,
                "final_miss_rate": summary.final_miss_rate,
                "mean_raw_recall": summary.mean_raw_recall,
                "mean_pass_a_recall": summary.mean_pass_a_recall,
                "mean_final_grounding": summary.mean_final_grounding,
                "ledger_jsonl": str(ledger_jsonl_path),
                "ledger_csv": str(ledger_csv_path),
                "summary_runs_tsv": str(summary_path),
                "top_failures_tsv": str(top_failures_path),
            },
            ensure_ascii=True,
            indent=2,
        ),
        encoding="utf-8",
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
