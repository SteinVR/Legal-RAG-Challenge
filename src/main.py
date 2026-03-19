"""CLI entrypoint for configuration-driven phase sync commands."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable, Sequence

import httpx

from src.common.config import DEFAULT_CONFIG_PATH, AppConfig, ConfigError, load_app_config
from src.common.schemas import Phase
from src.evaluation.contracts import (
    UnanswerableRetrievalPolicy,
    load_assistant_score_records,
    load_question_records,
    load_reference_records,
    load_submission_payload,
    question_types_from_questions,
)
from src.evaluation.dev_benchmark import (
    BenchmarkMetadataRecord,
    LegacyBenchmarkSummaryReport,
    analyze_run_consistency,
    analyze_benchmark_consistency,
    benchmark_submission,
    build_benchmark_report,
    compare_benchmark_runs,
    compare_benchmark_reports,
    load_benchmark_run_report,
)
from src.evaluation.scorer import ScoreOptions, score_submission
from src.evaluation.validator import SubmissionValidator, ValidationPolicy, build_corpus_registry
from src.submission.api_client import CompetitionApiClient
from src.submission.sync import CommandResult, PhasePaths, PhaseSyncService

ClientFactory = Callable[[AppConfig], CompetitionApiClient]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Agentic RAG Challenge CLI")
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="Path to the YAML config file.",
    )
    parser.add_argument("--env-file", default=".env", help="Path to the env file used for API credentials.")

    subparsers = parser.add_subparsers(dest="command", required=True)

    _add_download_questions_command(subparsers)
    _add_download_documents_command(subparsers)
    _add_sync_command(subparsers)
    _add_submit_command(subparsers)
    _add_submission_status_command(subparsers)
    _add_validate_submission_command(subparsers)
    _add_score_submission_command(subparsers)
    _add_benchmark_summary_command(subparsers)
    _add_compare_benchmark_runs_command(subparsers)
    _add_analyze_benchmark_consistency_command(subparsers)

    return parser


def _add_download_questions_command(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("download-questions", help="Download questions for the declared local phase.")
    parser.add_argument("--phase", choices=[phase.value for phase in Phase], help="Override the config phase.")
    parser.add_argument("--dry-run", action="store_true", help="Resolve config and paths without making API calls.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing local questions JSON.")


def _add_download_documents_command(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("download-documents", help="Download the documents ZIP for the declared phase.")
    parser.add_argument("--phase", choices=[phase.value for phase in Phase], help="Override the config phase.")
    parser.add_argument("--dry-run", action="store_true", help="Resolve config and paths without making API calls.")
    parser.add_argument("--force", action="store_true", help="Overwrite the local documents ZIP and extracted PDFs.")
    parser.add_argument(
        "--extract",
        dest="extract_documents",
        action="store_true",
        default=None,
        help="Extract PDFs after downloading the ZIP.",
    )
    parser.add_argument(
        "--no-extract",
        dest="extract_documents",
        action="store_false",
        help="Keep only the ZIP archive without extracting PDFs.",
    )


def _add_sync_command(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    for command_name in ("sync", "sync-phase"):
        parser = subparsers.add_parser(command_name, help="Download questions and documents for the declared phase.")
        parser.add_argument("--phase", choices=[phase.value for phase in Phase], help="Override the config phase.")
        parser.add_argument("--dry-run", action="store_true", help="Resolve config and paths without making API calls.")
        parser.add_argument("--force", action="store_true", help="Overwrite existing local download artifacts.")
        parser.add_argument(
            "--extract",
            dest="extract_documents",
            action="store_true",
            default=None,
            help="Extract PDFs after downloading the ZIP.",
        )
        parser.add_argument(
            "--no-extract",
            dest="extract_documents",
            action="store_false",
            help="Keep only the ZIP archive without extracting PDFs.",
        )


def _add_submit_command(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("submit", help="Submit submission.json and code archive to the platform.")
    parser.add_argument("--submission-path", required=True)
    parser.add_argument("--code-archive-path", required=True)


def _add_submission_status_command(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("submission-status", help="Query submission processing status.")
    parser.add_argument("--submission-uuid", required=True)


def _add_validate_submission_command(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("validate-submission", help="Validate a submission.json against local rules.")
    parser.add_argument("--submission-path", required=True)
    parser.add_argument("--questions-path", help="Path to questions.json. Defaults to the phase-local questions file.")
    parser.add_argument(
        "--documents-dir",
        help=(
            "Path to extracted PDFs. Defaults to the phase-local documents/pdfs directory "
            "when it exists."
        ),
    )
    parser.add_argument("--output-path", help="Optional JSON report destination.")


def _add_score_submission_command(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("score-submission", help="Score a submission against a local reference set.")
    parser.add_argument("--submission-path", required=True)
    parser.add_argument("--reference-path", required=True, help="Path to reference answers JSON/JSONL.")
    parser.add_argument(
        "--questions-path",
        help="Path to questions.json used to validate raw extra answers. Defaults to the phase-local questions file.",
    )
    parser.add_argument(
        "--assistant-scores-path",
        help="Optional manual/proxy free_text scores JSON/JSONL for this submission.",
    )
    parser.add_argument(
        "--documents-dir",
        help=(
            "Path to extracted PDFs used for doc/page validation. Defaults to the phase-local "
            "documents/pdfs directory when it exists."
        ),
    )
    parser.add_argument("--output-path", help="Optional JSON report destination.")


def _add_benchmark_summary_command(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "benchmark-summary",
        help="Run a submission against a structured dev benchmark dataset and compute slice metrics.",
    )
    parser.add_argument("--submission-path", required=True)
    parser.add_argument("--benchmark-path", help="Path to benchmark dataset JSON.")
    parser.add_argument("--reference-path", help="Path to reference answers JSON/JSONL.")
    parser.add_argument("--metadata-path", help="Path to benchmark metadata JSON/JSONL.")
    parser.add_argument("--benchmark-name", help="Logical benchmark name used in the report.")
    parser.add_argument("--questions-path", help="Path to questions.json. Defaults to the phase-local questions file.")
    parser.add_argument("--assistant-scores-path", help="Optional free_text assistant scores JSON/JSONL.")
    parser.add_argument(
        "--documents-dir",
        help=(
            "Path to extracted PDFs used for doc/page validation. Defaults to the phase-local "
            "documents/pdfs directory when it exists."
        ),
    )
    parser.add_argument("--label", help="Optional run label stored in the benchmark report.")
    parser.add_argument("--config-version", help="Optional config version stored in the benchmark report.")
    parser.add_argument("--submission-uuid", help="Optional submission UUID stored in the benchmark report.")
    parser.add_argument("--output-path", help="Optional JSON report destination.")


def _add_compare_benchmark_runs_command(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "compare-benchmark-runs",
        help="Compare two serialized benchmark run reports.",
    )
    parser.add_argument("--baseline-path", required=True)
    parser.add_argument("--candidate-path", required=True)
    parser.add_argument("--baseline-label")
    parser.add_argument("--candidate-label")
    parser.add_argument("--output-path", help="Optional JSON report destination.")


def _add_analyze_benchmark_consistency_command(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser(
        "analyze-benchmark-consistency",
        help="Analyze repeated benchmark runs for unstable questions.",
    )
    parser.add_argument(
        "--report-path",
        dest="report_paths",
        action="append",
        required=True,
        help="Path to a benchmark run JSON. Pass multiple times for repeated runs.",
    )
    parser.add_argument("--instability-threshold", type=float, default=0.05)
    parser.add_argument("--output-path", help="Optional JSON report destination.")


def main(argv: Sequence[str] | None = None, client_factory: ClientFactory | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        phase_override = getattr(args, "phase", None)
        config = load_app_config(Path(args.config), env_file=Path(args.env_file), phase_override=phase_override)
        result = _run_command(args, config, client_factory or CompetitionApiClient.from_config)
    except (ConfigError, ValueError, OSError, httpx.HTTPError) as exc:
        parser.exit(status=1, message=f"error: {exc}\n")
        return 1

    print(result)
    return 0


def _run_command(args: argparse.Namespace, config: AppConfig, client_factory: ClientFactory) -> str:
    if args.command in {"download-questions", "download-documents", "sync", "sync-phase"}:
        service = PhaseSyncService(config)
        result = _run_phase_command(args, service, config, client_factory)
        return _format_result(result)
    if args.command == "submit":
        return _run_submit(args, config, client_factory)
    if args.command == "submission-status":
        return _run_submission_status(args, config, client_factory)
    if args.command == "validate-submission":
        return _run_validate_submission(args, config)
    if args.command == "score-submission":
        return _run_score_submission(args, config)
    if args.command == "benchmark-summary":
        return _run_benchmark_summary(args, config)
    if args.command == "compare-benchmark-runs":
        return _run_compare_benchmark_runs(args)
    if args.command == "analyze-benchmark-consistency":
        return _run_analyze_benchmark_consistency(args)
    raise ValueError(f"Unsupported command: {args.command}")


def _run_phase_command(
    args: argparse.Namespace,
    service: PhaseSyncService,
    config: AppConfig,
    client_factory: ClientFactory,
) -> CommandResult:
    if args.command == "download-questions":
        return _run_with_optional_client(
            config,
            args.dry_run,
            client_factory,
            lambda client: service.download_questions(
                client=client,
                dry_run=args.dry_run,
                overwrite=args.force,
            ),
        )

    if args.command == "download-documents":
        return _run_with_optional_client(
            config,
            args.dry_run,
            client_factory,
            lambda client: service.download_documents(
                client=client,
                dry_run=args.dry_run,
                overwrite=args.force,
                extract_documents=args.extract_documents,
            ),
        )

    return _run_with_optional_client(
        config,
        args.dry_run,
        client_factory,
        lambda client: service.sync_phase(
            client=client,
            dry_run=args.dry_run,
            overwrite=args.force,
            extract_documents=args.extract_documents,
        ),
    )


def _run_with_optional_client(
    config: AppConfig,
    dry_run: bool,
    client_factory: ClientFactory,
    runner: Callable[[CompetitionApiClient | None], CommandResult],
) -> CommandResult:
    if dry_run:
        return runner(None)

    client = client_factory(config)
    try:
        return runner(client)
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()


def _run_submit(args: argparse.Namespace, config: AppConfig, client_factory: ClientFactory) -> str:
    return _run_with_client_json(
        config,
        client_factory,
        lambda client: client.submit_submission(args.submission_path, args.code_archive_path),
    )


def _run_submission_status(args: argparse.Namespace, config: AppConfig, client_factory: ClientFactory) -> str:
    return _run_with_client_json(
        config,
        client_factory,
        lambda client: client.get_submission_status(args.submission_uuid),
    )


def _run_with_client_json(
    config: AppConfig,
    client_factory: ClientFactory,
    runner: Callable[[CompetitionApiClient], Any],
) -> str:
    client = client_factory(config)
    try:
        result = runner(client)
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()
    return json.dumps(result, ensure_ascii=False)


def _run_validate_submission(args: argparse.Namespace, config: AppConfig) -> str:
    questions_path = _resolve_questions_path(args.questions_path, config)

    documents_dir = _resolve_documents_dir(args.documents_dir, config, required=True)
    question_types = question_types_from_questions(load_question_records(questions_path))
    submission_payload = load_submission_payload(args.submission_path)
    validator = SubmissionValidator(
        question_types=question_types,
        corpus_registry=build_corpus_registry(documents_dir),
        policy=ValidationPolicy(
            unanswerable_retrieval_policy=UnanswerableRetrievalPolicy(
                config.evaluation.unanswerable_retrieval_policy
            ),
            require_full_question_coverage=True,
            emit_ambiguity_warning=True,
        ),
    )
    report = validator.validate(submission_payload)
    return _serialize_report(report, output_path=args.output_path)


def _run_score_submission(args: argparse.Namespace, config: AppConfig) -> str:
    questions_path = _resolve_questions_path(args.questions_path, config)

    documents_dir = _resolve_documents_dir(args.documents_dir, config, required=True)
    submission_payload = load_submission_payload(args.submission_path)
    references = load_reference_records(args.reference_path)
    validation_question_types = question_types_from_questions(load_question_records(questions_path))
    assistant_scores = (
        load_assistant_score_records(args.assistant_scores_path) if args.assistant_scores_path else None
    )
    report = score_submission(
        submission_payload,
        references=references,
        assistant_scores=assistant_scores,
        options=ScoreOptions(
            unanswerable_retrieval_policy=UnanswerableRetrievalPolicy(
                config.evaluation.unanswerable_retrieval_policy
            ),
            documents_dir=str(documents_dir),
            validation_question_types=validation_question_types,
        ),
    )
    return _serialize_report(report, output_path=args.output_path)


def _run_benchmark_summary(args: argparse.Namespace, config: AppConfig) -> str:
    questions_path = _resolve_questions_path(args.questions_path, config)
    documents_dir = _resolve_documents_dir(args.documents_dir, config, required=True)
    if args.benchmark_path:
        report = benchmark_submission(
            submission_path=args.submission_path,
            benchmark_path=args.benchmark_path,
            questions_path=questions_path,
            documents_dir=documents_dir,
            assistant_scores_path=args.assistant_scores_path,
            run_label=args.label,
            config_version=args.config_version,
            submission_uuid=args.submission_uuid,
            unanswerable_retrieval_policy=UnanswerableRetrievalPolicy(
                config.evaluation.unanswerable_retrieval_policy
            ),
        )
    else:
        if not args.reference_path or not args.metadata_path or not args.benchmark_name:
            raise ValueError(
                "benchmark-summary requires either --benchmark-path or the trio "
                "--reference-path, --metadata-path, and --benchmark-name."
            )
        submission_payload = load_submission_payload(args.submission_path)
        references = load_reference_records(args.reference_path)
        questions = load_question_records(questions_path)
        metadata_payload = load_submission_payload(args.metadata_path)
        metadata_rows = metadata_payload.get("metadata") if isinstance(metadata_payload, dict) else metadata_payload
        if not isinstance(metadata_rows, list):
            raise ValueError(f"Expected benchmark metadata array in {args.metadata_path}.")
        metadata = [BenchmarkMetadataRecord.model_validate(row) for row in metadata_rows]
        assistant_scores = (
            load_assistant_score_records(args.assistant_scores_path) if args.assistant_scores_path else None
        )
        report = build_benchmark_report(
            submission_payload,
            benchmark_name=args.benchmark_name,
            references=references,
            questions=questions,
            metadata=metadata,
            assistant_scores=assistant_scores,
            options=ScoreOptions(
                unanswerable_retrieval_policy=UnanswerableRetrievalPolicy(
                    config.evaluation.unanswerable_retrieval_policy
                ),
                documents_dir=str(documents_dir),
                validation_question_types=question_types_from_questions(questions),
            ),
        )
    return _serialize_report(report, output_path=args.output_path)


def _run_compare_benchmark_runs(args: argparse.Namespace) -> str:
    baseline_payload = load_submission_payload(args.baseline_path)
    candidate_payload = load_submission_payload(args.candidate_path)
    if isinstance(baseline_payload, dict) and "run_metadata" in baseline_payload:
        baseline = load_benchmark_run_report(args.baseline_path)
        candidate = load_benchmark_run_report(args.candidate_path)
        report = compare_benchmark_runs(baseline, candidate)
    else:
        report = compare_benchmark_reports(
            LegacyBenchmarkSummaryReport.model_validate(baseline_payload),
            LegacyBenchmarkSummaryReport.model_validate(candidate_payload),
            baseline_label=args.baseline_label or "baseline",
            candidate_label=args.candidate_label or "candidate",
        )
    return _serialize_report(report, output_path=args.output_path)


def _run_analyze_benchmark_consistency(args: argparse.Namespace) -> str:
    first_payload = load_submission_payload(args.report_paths[0])
    if isinstance(first_payload, dict) and "run_metadata" in first_payload:
        reports = [load_benchmark_run_report(path) for path in args.report_paths]
        report = analyze_run_consistency(
            reports,
            instability_threshold=args.instability_threshold,
        )
    else:
        reports = [
            LegacyBenchmarkSummaryReport.model_validate(load_submission_payload(path)) for path in args.report_paths
        ]
        report = analyze_benchmark_consistency(
            reports,
            instability_threshold=args.instability_threshold,
        )
    return _serialize_report(report, output_path=args.output_path)


def _format_result(result: CommandResult) -> str:
    lines = [
        f"command: {result.command}",
        f"phase: {result.phase}",
        f"dry_run: {str(result.dry_run).lower()}",
        f"manifest: {result.manifest_path}",
    ]

    if result.questions_count is not None:
        lines.append(f"questions_count: {result.questions_count}")

    if result.extracted_pdf_count is not None:
        lines.append(f"extracted_pdf_count: {result.extracted_pdf_count}")

    if result.planned_paths:
        lines.append("planned_paths:")
        lines.extend(f"  - {path}" for path in result.planned_paths)

    if result.written_paths:
        lines.append("written_paths:")
        lines.extend(f"  - {path}" for path in result.written_paths)

    if result.skipped_paths:
        lines.append("skipped_paths:")
        lines.extend(f"  - {path}" for path in result.skipped_paths)

    return "\n".join(lines)


def _default_questions_path(config: AppConfig) -> Path:
    return PhasePaths.from_config(config).questions_path


def _default_documents_dir(config: AppConfig) -> Path:
    return PhasePaths.from_config(config).documents_extract_dir


def _resolve_questions_path(raw_questions_path: str | None, config: AppConfig) -> Path:
    questions_path = Path(raw_questions_path) if raw_questions_path else _default_questions_path(config)
    if not questions_path.exists():
        raise ValueError(
            f"Questions file does not exist: {questions_path}. Run sync-phase first or pass --questions-path."
        )
    return questions_path


def _resolve_documents_dir(raw_documents_dir: str | None, config: AppConfig, *, required: bool = False) -> Path | None:
    if raw_documents_dir:
        resolved_path = Path(raw_documents_dir)
        if required and not resolved_path.exists():
            raise ValueError(f"Documents directory does not exist: {resolved_path}")
        return resolved_path

    default_documents_dir = _default_documents_dir(config)
    if default_documents_dir.exists():
        return default_documents_dir
    if required:
        raise ValueError(
            "Documents directory does not exist. Run sync-phase first or pass --documents-dir "
            "to enable corpus-backed telemetry validation."
        )
    return None


def _serialize_report(report, *, output_path: str | None) -> str:
    payload = json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2)
    if output_path:
        Path(output_path).write_text(f"{payload}\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    raise SystemExit(main())
