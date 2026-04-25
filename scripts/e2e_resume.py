#!/usr/bin/env python3
"""Checkpointed end-to-end runner for warmup/full pipelines.

This runner provides two resume-safe layers:
1. Answer generation resume via `build-submission` QA checkpoints.
2. Local benchmark resume via per-question scoring checkpoint JSONL.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.common.config import load_app_config
from src.common.schemas import Phase
from src.evaluation.contracts import (
    AnswerScoreBreakdown,
    AnswerType,
    ScoreMetrics,
    ScoreReport,
    UnanswerableRetrievalPolicy,
    flatten_page_references,
    load_assistant_score_records,
    load_question_records,
    load_reference_records,
    load_submission_payload,
    question_types_from_questions,
    question_types_from_references,
)
from src.evaluation.dev_benchmark.models import BenchmarkRunReport, BenchmarkSliceReport
from src.evaluation.dev_benchmark.runtime import (
    build_default_slices,
    compare_benchmark_reports,
    load_benchmark_dataset,
    load_benchmark_run_report,
)
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
from src.evaluation.scorer import (
    MISSING_ASSISTANT_SCORE_NOTE,
    NO_DETERMINISTIC_NOTE,
    NO_FREE_TEXT_NOTE,
    PARTIAL_FREE_TEXT_SCORES_NOTE,
    TTFT_PROXY_NOTE,
    score_deterministic_answer,
    score_grounding,
    score_ttft,
)
from src.evaluation.validator import (
    SubmissionValidator,
    ValidationPolicy,
    build_corpus_registry,
    collect_answer_dicts,
    extract_retrieved_pairs,
    extract_ttft_ms,
)


@dataclass(slots=True)
class E2EArtifacts:
    """Resolved artifact paths for one e2e run."""

    run_dir: Path
    warmup_root: Path
    runs_root: Path
    submission_dir: Path
    eval_dir: Path
    grounding_dir: Path
    manifest_path: Path
    submission_path: Path
    qa_checkpoint_path: Path
    benchmark_report_path: Path
    benchmark_checkpoint_path: Path
    comparison_report_path: Path
    validation_report_path: Path
    grounding_ledger_jsonl_path: Path
    grounding_ledger_csv_path: Path
    grounding_summary_json_path: Path
    summary_runs_tsv_path: Path
    top_failures_tsv_path: Path


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(description="Checkpointed e2e runner for warmup/full.")
    parser.add_argument("--config", default="configs/baseline/v001/config.yaml")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--phase", choices=[phase.value for phase in Phase], required=True)
    parser.add_argument("--questions-path", required=True)
    parser.add_argument("--documents-dir", required=True)
    parser.add_argument("--output-dir", required=True, help="Run bundle directory for one e2e execution.")
    parser.add_argument("--checkpoint-every", type=int, default=1)
    parser.add_argument("--no-resume", action="store_true", help="Disable checkpoint resume.")
    parser.add_argument("--benchmark-path", help="Optional benchmark dataset path for local evaluation.")
    parser.add_argument("--assistant-scores-path", help="Optional assistant scores path.")
    parser.add_argument("--benchmark-output-path", help="Optional benchmark report output path.")
    parser.add_argument("--run-label", help="Optional note appended to benchmark report.")
    parser.add_argument("--config-version", help="Optional config version note.")
    parser.add_argument("--submission-uuid", help="Optional submission UUID note.")
    parser.add_argument("--compare-against", help="Optional previous benchmark report path for delta.")
    parser.add_argument("--comparison-output-path", help="Optional comparison report output path.")
    return parser.parse_args()


def _resolve_artifacts(run_dir: Path, args: argparse.Namespace) -> E2EArtifacts:
    """Resolve structured output paths for one warmup run bundle."""

    submission_dir = run_dir / "submission"
    eval_dir = run_dir / "eval"
    grounding_dir = run_dir / "grounding"
    warmup_root = run_dir.parent.parent if run_dir.parent.name == "runs" else run_dir.parent
    runs_root = warmup_root / "runs"

    return E2EArtifacts(
        run_dir=run_dir,
        warmup_root=warmup_root,
        runs_root=runs_root,
        submission_dir=submission_dir,
        eval_dir=eval_dir,
        grounding_dir=grounding_dir,
        manifest_path=run_dir / "manifest.json",
        submission_path=submission_dir / "submission.json",
        qa_checkpoint_path=submission_dir / "qa_checkpoint.json",
        benchmark_report_path=(
            Path(args.benchmark_output_path) if args.benchmark_output_path else eval_dir / "benchmark_report.json"
        ),
        benchmark_checkpoint_path=eval_dir / "benchmark_answer_scores.checkpoint.jsonl",
        comparison_report_path=(
            Path(args.comparison_output_path)
            if args.comparison_output_path
            else eval_dir / "comparison_vs_previous.json"
        ),
        validation_report_path=eval_dir / "validation_report.json",
        grounding_ledger_jsonl_path=grounding_dir / "ledger.jsonl",
        grounding_ledger_csv_path=grounding_dir / "ledger.csv",
        grounding_summary_json_path=grounding_dir / "summary.json",
        summary_runs_tsv_path=warmup_root / "summary_runs.tsv",
        top_failures_tsv_path=warmup_root / "top_failures.tsv",
    )


def _write_grounding_artifacts(
    *,
    run_id: str,
    artifacts: E2EArtifacts,
    submission_path: Path,
    benchmark_path: Path,
) -> dict[str, Any]:
    """Build per-run grounding artifacts plus aggregate warmup summaries."""

    submission_payload = load_submission_payload(submission_path)
    references = load_reference_records(benchmark_path)
    rows = build_grounding_ledger_rows(
        run_id=run_id,
        submission_payload=submission_payload,
        references=references,
    )
    summary = build_grounding_summary(run_id=run_id, rows=rows)

    write_grounding_ledger_jsonl(path=artifacts.grounding_ledger_jsonl_path, rows=rows)
    write_grounding_ledger_csv(path=artifacts.grounding_ledger_csv_path, rows=rows)
    upsert_summary_row(path=artifacts.summary_runs_tsv_path, summary=summary)
    top_failures = build_top_failures_from_runs_dir(
        runs_dir=artifacts.runs_root,
        top_n=20,
    )
    write_top_failures_tsv(path=artifacts.top_failures_tsv_path, rows=top_failures)

    grounding_summary_payload = build_grounding_summary_payload(
        summary=summary,
        rows=rows,
        ledger_jsonl_path=artifacts.grounding_ledger_jsonl_path,
        ledger_csv_path=artifacts.grounding_ledger_csv_path,
        summary_runs_tsv_path=artifacts.summary_runs_tsv_path,
        top_failures_tsv_path=artifacts.top_failures_tsv_path,
    )
    _write_json(artifacts.grounding_summary_json_path, grounding_summary_payload)
    return grounding_summary_payload


def _build_manifest_payload(
    *,
    args: argparse.Namespace,
    artifacts: E2EArtifacts,
    benchmark_report: BenchmarkRunReport | None,
    grounding_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build run-manifest payload for one structured warmup run bundle."""

    return {
        "run_id": artifacts.run_dir.name,
        "phase": args.phase,
        "questions_path": str(Path(args.questions_path)),
        "documents_dir": str(Path(args.documents_dir)),
        "config_path": str(Path(args.config)),
        "env_file": str(Path(args.env_file)),
        "run_label": args.run_label,
        "artifacts": {
            "submission_dir": str(artifacts.submission_dir),
            "eval_dir": str(artifacts.eval_dir),
            "grounding_dir": str(artifacts.grounding_dir),
            "warmup_root": str(artifacts.warmup_root),
            "submission_json": str(artifacts.submission_path),
            "qa_checkpoint_json": str(artifacts.qa_checkpoint_path),
            "trace_manifest_json": str(artifacts.submission_dir / "trace_manifest.json"),
            "traces_dir": str(artifacts.submission_dir / "traces"),
            "code_archive_zip": str(artifacts.submission_dir / "code_archive.zip"),
            "benchmark_report_json": str(artifacts.benchmark_report_path) if benchmark_report is not None else None,
            "benchmark_scores_jsonl": str(artifacts.benchmark_checkpoint_path)
            if benchmark_report is not None
            else None,
            "comparison_json": str(artifacts.comparison_report_path)
            if artifacts.comparison_report_path.exists()
            else None,
            "validation_report_json": str(artifacts.validation_report_path)
            if artifacts.validation_report_path.exists()
            else None,
            "grounding_summary_json": str(artifacts.grounding_summary_json_path)
            if grounding_summary is not None
            else None,
            "grounding_ledger_jsonl": str(artifacts.grounding_ledger_jsonl_path)
            if grounding_summary is not None
            else None,
            "grounding_ledger_csv": str(artifacts.grounding_ledger_csv_path) if grounding_summary is not None else None,
            "summary_runs_tsv": str(artifacts.summary_runs_tsv_path) if grounding_summary is not None else None,
            "top_failures_tsv": str(artifacts.top_failures_tsv_path) if grounding_summary is not None else None,
        },
        "benchmark": (
            {
                "benchmark_id": benchmark_report.benchmark_id,
                "reference_count": benchmark_report.reference_count,
                "assistant_score_count": benchmark_report.assistant_score_count,
                "overall_metrics": benchmark_report.overall.metrics.model_dump(mode="json"),
            }
            if benchmark_report is not None
            else None
        ),
        "grounding": grounding_summary,
    }


def _run_command(command: list[str]) -> None:
    """Run a subprocess command and fail fast on non-zero exit."""

    print(f"[run] {' '.join(command)}")
    subprocess.run(command, check=True)


def _run_build_submission(
    *,
    config_path: Path,
    env_file: Path,
    phase: str,
    questions_path: Path,
    documents_dir: Path,
    output_dir: Path,
    checkpoint_path: Path,
    checkpoint_every: int,
    resume: bool,
) -> None:
    """Run build-submission with checkpoint resume support."""

    command = [
        sys.executable,
        "-m",
        "src.main",
        "--config",
        str(config_path),
        "--env-file",
        str(env_file),
        "build-submission",
        "--phase",
        phase,
        "--questions-path",
        str(questions_path),
        "--documents-dir",
        str(documents_dir),
        "--output-dir",
        str(output_dir),
        "--checkpoint-path",
        str(checkpoint_path),
        "--checkpoint-every",
        str(checkpoint_every),
    ]
    if resume:
        command.append("--resume-from-checkpoint")
    _run_command(command)


def _run_validate_submission(
    *,
    config_path: Path,
    env_file: Path,
    phase: str,
    submission_path: Path,
    questions_path: Path,
    documents_dir: Path,
    output_path: Path,
) -> None:
    """Run local submission validation and write a JSON report."""

    command = [
        sys.executable,
        "-m",
        "src.main",
        "--config",
        str(config_path),
        "--env-file",
        str(env_file),
        "validate-submission",
        "--phase",
        phase,
        "--submission-path",
        str(submission_path),
        "--questions-path",
        str(questions_path),
        "--documents-dir",
        str(documents_dir),
        "--output-path",
        str(output_path),
    ]
    _run_command(command)


def _load_checkpoint_scores(checkpoint_path: Path) -> dict[str, AnswerScoreBreakdown]:
    """Load per-question answer scores from checkpoint JSONL."""

    if not checkpoint_path.exists():
        return {}
    scores: dict[str, AnswerScoreBreakdown] = {}
    with checkpoint_path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            payload = json.loads(line)
            entry = AnswerScoreBreakdown.model_validate(payload)
            scores[entry.question_id] = entry
    return scores


def _append_checkpoint_score(checkpoint_path: Path, score: AnswerScoreBreakdown) -> None:
    """Append one scored question to checkpoint JSONL."""

    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    with checkpoint_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(score.model_dump(mode="json"), ensure_ascii=False) + "\n")


def _mean_or_zero(values: list[float]) -> float:
    """Return arithmetic mean or 0.0 for empty lists."""

    if not values:
        return 0.0
    return sum(values) / len(values)


def _mean_or_none(values: list[float]) -> float | None:
    """Return arithmetic mean or None for empty lists."""

    if not values:
        return None
    return sum(values) / len(values)


def _build_score_metrics(answer_scores: list[AnswerScoreBreakdown]) -> ScoreMetrics:
    """Aggregate per-question score rows into submission-level metrics."""

    deterministic_values = [
        score.deterministic_score for score in answer_scores if score.deterministic_score is not None
    ]
    assistant_values = [score.assistant_score for score in answer_scores if score.assistant_score is not None]
    grounding_values = [score.grounding_score for score in answer_scores]
    telemetry_values = [score.telemetry_factor for score in answer_scores]
    ttft_values = [score.ttft_factor for score in answer_scores]
    ttft_ms_values = [score.ttft_ms for score in answer_scores if score.ttft_ms is not None]

    deterministic_metric = _mean_or_zero(deterministic_values)
    assistant_metric = _mean_or_zero(assistant_values)
    grounding_metric = _mean_or_zero(grounding_values)
    telemetry_metric = _mean_or_zero(telemetry_values)
    ttft_metric = _mean_or_zero(ttft_values)
    total_score = (
        (0.7 * deterministic_metric + 0.3 * assistant_metric) * grounding_metric * telemetry_metric * ttft_metric
    )

    return ScoreMetrics(
        deterministic=deterministic_metric,
        assistant=assistant_metric,
        grounding=grounding_metric,
        telemetry=telemetry_metric,
        ttft_ms=_mean_or_none(ttft_ms_values),
        ttft_multiplier=ttft_metric,
        total_score=total_score,
        deterministic_questions=len(deterministic_values),
        free_text_questions=len(assistant_values),
        scored_questions=len(answer_scores),
    )


def _build_score_notes(*, metrics: ScoreMetrics, assistant_scores_map_size: int) -> list[str]:
    """Build score-level notes matching the scorer contract."""

    notes = [TTFT_PROXY_NOTE]
    if metrics.deterministic_questions == 0:
        notes.append(NO_DETERMINISTIC_NOTE)
    if metrics.free_text_questions == 0:
        notes.append(NO_FREE_TEXT_NOTE)
    elif assistant_scores_map_size < metrics.free_text_questions:
        notes.append(PARTIAL_FREE_TEXT_SCORES_NOTE)
    return notes


def _run_benchmark_resume(
    *,
    submission_path: Path,
    benchmark_path: Path,
    questions_path: Path,
    documents_dir: Path,
    checkpoint_path: Path,
    assistant_scores_path: Path | None,
    run_label: str | None,
    config_version: str | None,
    submission_uuid: str | None,
    unanswerable_retrieval_policy: UnanswerableRetrievalPolicy,
) -> BenchmarkRunReport:
    """Run local benchmark with per-question checkpoint resume."""

    submission_payload = load_submission_payload(submission_path)
    dataset = load_benchmark_dataset(benchmark_path)
    questions = load_question_records(questions_path)
    assistant_scores = load_assistant_score_records(assistant_scores_path) if assistant_scores_path is not None else []
    assistant_score_map = {row.question_id: row.assistant_score for row in assistant_scores}

    validation = SubmissionValidator(
        question_types=question_types_from_questions(questions),
        required_question_ids=set(question_types_from_references(dataset.references)),
        corpus_registry=build_corpus_registry(str(documents_dir)),
        policy=ValidationPolicy(
            unanswerable_retrieval_policy=unanswerable_retrieval_policy,
            require_full_question_coverage=True,
            emit_ambiguity_warning=True,
        ),
    ).validate(submission_payload)
    telemetry_factor_map = {
        report.question_id: (0.9 if report.telemetry_malformed else 1.0)
        for report in validation.answers
        if report.question_id
    }

    answer_rows = collect_answer_dicts(submission_payload)
    answers_by_question_id = {
        row["question_id"]: row
        for row in answer_rows
        if isinstance(row, dict) and isinstance(row.get("question_id"), str)
    }

    checkpoint_scores = _load_checkpoint_scores(checkpoint_path)
    total_references = len(dataset.references)
    for index, reference in enumerate(dataset.references, start=1):
        if reference.question_id in checkpoint_scores:
            continue
        answer_payload = answers_by_question_id.get(reference.question_id)
        answer_notes: list[str] = []

        deterministic_score: float | None = None
        assistant_score: float | None = None
        if reference.answer_type != AnswerType.FREE_TEXT:
            deterministic_score = score_deterministic_answer(
                answer_type=reference.answer_type,
                predicted=answer_payload.get("answer") if answer_payload else None,
                expected=reference.answer,
            )
        else:
            assistant_score = assistant_score_map.get(reference.question_id)
            if assistant_score is None:
                assistant_score = 0.0
                answer_notes.append(MISSING_ASSISTANT_SCORE_NOTE)

        score_row = AnswerScoreBreakdown(
            question_id=reference.question_id,
            answer_type=reference.answer_type,
            deterministic_score=deterministic_score,
            assistant_score=assistant_score,
            grounding_score=score_grounding(
                predicted_pairs=extract_retrieved_pairs(answer_payload),
                gold_pairs=flatten_page_references(reference.gold_retrieval),
            ),
            telemetry_factor=telemetry_factor_map.get(reference.question_id, 0.9),
            ttft_ms=extract_ttft_ms(answer_payload),
            ttft_factor=score_ttft(extract_ttft_ms(answer_payload)),
            notes=answer_notes,
        )
        checkpoint_scores[reference.question_id] = score_row
        _append_checkpoint_score(checkpoint_path, score_row)
        if index % 50 == 0 or index == total_references:
            print(f"[eval] scored {index}/{total_references}")

    ordered_scores = [checkpoint_scores[reference.question_id] for reference in dataset.references]
    overall_metrics = _build_score_metrics(ordered_scores)
    overall_notes = _build_score_notes(
        metrics=overall_metrics,
        assistant_scores_map_size=len(assistant_score_map),
    )
    reference_question_ids = {reference.question_id for reference in dataset.references}
    unscored_question_ids = sorted(
        question_id for question_id in answers_by_question_id if question_id not in reference_question_ids
    )
    overall = ScoreReport(
        metrics=overall_metrics,
        validation=validation,
        answer_scores=ordered_scores,
        unscored_question_ids=unscored_question_ids,
        notes=overall_notes,
    )

    slices: list[BenchmarkSliceReport] = []
    for slice_id, label, slice_references in build_default_slices(dataset.references):
        slice_scores = [checkpoint_scores[reference.question_id] for reference in slice_references]
        slice_metrics = _build_score_metrics(slice_scores)
        slice_notes = _build_score_notes(
            metrics=slice_metrics,
            assistant_scores_map_size=len(assistant_score_map),
        )
        slice_question_ids = sorted(reference.question_id for reference in slice_references)
        slices.append(
            BenchmarkSliceReport(
                slice_id=slice_id,
                label=label,
                question_ids=slice_question_ids,
                question_count=len(slice_scores),
                score=ScoreReport(
                    metrics=slice_metrics,
                    validation=validation,
                    answer_scores=slice_scores,
                    unscored_question_ids=[qid for qid in unscored_question_ids if qid in set(slice_question_ids)],
                    notes=slice_notes,
                ),
            )
        )

    report = BenchmarkRunReport(
        benchmark_id=dataset.benchmark_id,
        title=dataset.title,
        reference_count=len(dataset.references),
        assistant_score_count=len(assistant_scores),
        overall=overall,
        slices=slices,
        notes=list(dataset.notes),
    )
    report.notes.extend(
        [
            note
            for note in (
                f"run_label={run_label}" if run_label else None,
                f"config_version={config_version}" if config_version else None,
                f"submission_uuid={submission_uuid}" if submission_uuid else None,
            )
            if note is not None
        ]
    )
    return report


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON payload to disk with pretty formatting."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    """Run checkpointed e2e workflow."""

    args = _parse_args()
    run_dir = Path(args.output_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    artifacts = _resolve_artifacts(run_dir, args)

    resume_enabled = not args.no_resume
    _run_build_submission(
        config_path=Path(args.config),
        env_file=Path(args.env_file),
        phase=args.phase,
        questions_path=Path(args.questions_path),
        documents_dir=Path(args.documents_dir),
        output_dir=artifacts.submission_dir,
        checkpoint_path=artifacts.qa_checkpoint_path,
        checkpoint_every=args.checkpoint_every,
        resume=resume_enabled,
    )

    benchmark_report: BenchmarkRunReport | None = None
    grounding_summary: dict[str, Any] | None = None
    if args.benchmark_path:
        config = load_app_config(Path(args.config), env_file=Path(args.env_file), phase_override=args.phase)
        benchmark_report = _run_benchmark_resume(
            submission_path=artifacts.submission_path,
            benchmark_path=Path(args.benchmark_path),
            questions_path=Path(args.questions_path),
            documents_dir=Path(args.documents_dir),
            checkpoint_path=artifacts.benchmark_checkpoint_path,
            assistant_scores_path=Path(args.assistant_scores_path) if args.assistant_scores_path else None,
            run_label=args.run_label,
            config_version=args.config_version,
            submission_uuid=args.submission_uuid,
            unanswerable_retrieval_policy=UnanswerableRetrievalPolicy(config.evaluation.unanswerable_retrieval_policy),
        )
        _write_json(artifacts.benchmark_report_path, benchmark_report.model_dump(mode="json"))
        print(f"[ok] benchmark report: {artifacts.benchmark_report_path}")

        if args.compare_against:
            baseline = load_benchmark_run_report(Path(args.compare_against))
            comparison = compare_benchmark_reports(
                baseline,
                benchmark_report,
                baseline_label="previous",
                candidate_label="current",
            )
            _write_json(artifacts.comparison_report_path, comparison.model_dump(mode="json"))
            print(f"[ok] comparison report: {artifacts.comparison_report_path}")

        grounding_summary = _write_grounding_artifacts(
            run_id=artifacts.run_dir.name,
            artifacts=artifacts,
            submission_path=artifacts.submission_path,
            benchmark_path=Path(args.benchmark_path),
        )
        print(f"[ok] grounding summary: {artifacts.grounding_summary_json_path}")
    else:
        if resume_enabled and artifacts.validation_report_path.exists():
            print(f"[resume] validation report already exists: {artifacts.validation_report_path}")
        else:
            _run_validate_submission(
                config_path=Path(args.config),
                env_file=Path(args.env_file),
                phase=args.phase,
                submission_path=artifacts.submission_path,
                questions_path=Path(args.questions_path),
                documents_dir=Path(args.documents_dir),
                output_path=artifacts.validation_report_path,
            )
        print(f"[ok] validation report: {artifacts.validation_report_path}")

    _write_json(
        artifacts.manifest_path,
        _build_manifest_payload(
            args=args,
            artifacts=artifacts,
            benchmark_report=benchmark_report,
            grounding_summary=grounding_summary,
        ),
    )
    print(f"[ok] run manifest: {artifacts.manifest_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
