"""CLI entrypoint for configuration-driven phase sync commands."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable, Sequence

import httpx

from src.common.config import DEFAULT_CONFIG_PATH, AppConfig, ConfigError, load_app_config
from src.common.schemas import Phase
from src.submission.api_client import CompetitionApiClient
from src.submission.sync import CommandResult, PhaseSyncService

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
    client = client_factory(config)
    try:
        result = client.submit_submission(args.submission_path, args.code_archive_path)
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()
    return json.dumps(result, ensure_ascii=False)


def _run_submission_status(args: argparse.Namespace, config: AppConfig, client_factory: ClientFactory) -> str:
    client = client_factory(config)
    try:
        result = client.get_submission_status(args.submission_uuid)
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()
    return json.dumps(result, ensure_ascii=False)


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


if __name__ == "__main__":
    raise SystemExit(main())
