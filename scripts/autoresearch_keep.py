#!/usr/bin/env python3
"""Persist agent-decided autoresearch decisions with config snapshots.

This helper records keep/discard/crash decisions selected by the agent.
It does not choose winners automatically. It only logs decision metadata,
persists history/state, and snapshots configs for explicit keep decisions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_AUTORESEARCH_METRIC_PREFIX = "AUTORESEARCH_METRIC "
_SAFE_TOKEN_PATTERN = re.compile(r"[^a-zA-Z0-9._-]+")
_HISTORY_HEADER = (
    "timestamp_utc",
    "run_id",
    "commit",
    "status",
    "metric_key",
    "metric_value",
    "runtime_sec",
    "metrics_json",
    "config_path",
    "config_sha256",
    "config_snapshot_path",
    "promoted_config_path",
    "description",
)


@dataclass(slots=True, frozen=True)
class RunMetrics:
    """Parsed metric payload from one run log."""

    values: dict[str, float]
    raw_line: str


@dataclass(slots=True, frozen=True)
class RunDecision:
    """Decision payload persisted for one run."""

    status: str
    metric_key: str
    metric_value: float
    runtime_sec: float
    keep_ref: str
    config_snapshot_path: str
    promoted_config_path: str


def _build_parser() -> argparse.ArgumentParser:
    """Build command-line parser for explicit keep/discard/crash persistence."""

    parser = argparse.ArgumentParser(description="Persist explicit autoresearch decisions.")
    parser.add_argument("--run-id", required=True, help="Logical run tag, e.g. apr06-grounding.")
    parser.add_argument(
        "--status",
        required=True,
        choices=("keep", "discard", "crash"),
        help="Decision selected by the agent for this run.",
    )
    parser.add_argument("--run-log", required=True, help="Path to run log containing AUTORESEARCH_METRIC.")
    parser.add_argument("--config-path", required=True, help="Path to config file used by this run.")
    parser.add_argument("--metric-key", default="grounding_mean", help="Primary metric key to optimize.")
    parser.add_argument("--keep-ref", default="", help="Optional explicit keep_ref chosen by the agent.")
    parser.add_argument(
        "--state-path",
        default="analysis/grounding/keep_state.json",
        help="Tracked JSON keep-state path.",
    )
    parser.add_argument(
        "--history-path",
        default="analysis/grounding/keep_history.tsv",
        help="Tracked TSV history path.",
    )
    parser.add_argument(
        "--kept-config-dir",
        default="analysis/grounding/kept_configs",
        help="Tracked directory where kept config snapshots are stored.",
    )
    parser.add_argument(
        "--promote-config-path",
        default="",
        help="Optional canonical config path to overwrite when status=keep.",
    )
    parser.add_argument(
        "--description",
        default="",
        help="Short note describing the attempted change.",
    )
    return parser


def _utc_now_iso() -> str:
    """Return current UTC timestamp in compact ISO-like form."""

    return datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _safe_token(value: str) -> str:
    """Sanitize free-form strings for filesystem-safe filename tokens."""

    sanitized = _SAFE_TOKEN_PATTERN.sub("-", str(value).strip())
    sanitized = sanitized.strip("-")
    return sanitized or "na"


def _parse_metric_value(raw_value: str) -> float:
    """Parse one metric value token as float."""

    value = float(raw_value)
    if value != value:  # NaN check
        raise ValueError("Metric value is NaN.")
    return value


def _parse_autoresearch_metrics(run_log_text: str) -> RunMetrics | None:
    """Extract final AUTORESEARCH_METRIC payload from run log text."""

    metric_line = ""
    for line in run_log_text.splitlines():
        if line.startswith(_AUTORESEARCH_METRIC_PREFIX):
            metric_line = line.strip()
    if not metric_line:
        return None

    payload: dict[str, float] = {}
    for token in metric_line[len(_AUTORESEARCH_METRIC_PREFIX) :].split():
        if "=" not in token:
            continue
        key, raw_value = token.split("=", 1)
        try:
            payload[str(key)] = _parse_metric_value(raw_value)
        except ValueError:
            continue
    if not payload:
        return None
    return RunMetrics(values=payload, raw_line=metric_line)


def _load_json(path: Path) -> dict[str, Any]:
    """Load JSON object from disk or return empty default."""

    if not path.exists():
        return {}
    content = path.read_text(encoding="utf-8").strip()
    if not content:
        return {}
    loaded = json.loads(content)
    if isinstance(loaded, dict):
        return loaded
    raise ValueError(f"Expected JSON object at {path}, got {type(loaded).__name__}.")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON object with deterministic formatting."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_run_metrics(path: Path) -> RunMetrics | None:
    """Read run log and parse final AUTORESEARCH_METRIC payload."""

    if not path.exists():
        return None
    return _parse_autoresearch_metrics(path.read_text(encoding="utf-8"))


def _compute_sha256(path: Path) -> str:
    """Compute file-level SHA256 hash."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_commit_ref() -> str:
    """Return short git commit hash with dirty suffix when applicable."""

    revision_proc = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    revision = revision_proc.stdout.strip() if revision_proc.returncode == 0 else "uncommitted"
    if not revision:
        revision = "uncommitted"

    dirty_proc = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        check=False,
        capture_output=True,
        text=True,
    )
    if dirty_proc.returncode == 0 and dirty_proc.stdout.strip():
        return f"{revision}-dirty"
    return revision


def _append_history_row(path: Path, row: dict[str, str]) -> None:
    """Append one run decision row to TSV history, creating header if needed."""

    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        header = "\t".join(_HISTORY_HEADER)
        path.write_text(header + "\n", encoding="utf-8")

    ordered_values = [row.get(column, "") for column in _HISTORY_HEADER]
    escaped_values = [str(value).replace("\t", " ").replace("\n", " ").strip() for value in ordered_values]
    with path.open("a", encoding="utf-8") as handle:
        handle.write("\t".join(escaped_values) + "\n")


def _copy_config_snapshot(
    *,
    source_config: Path,
    kept_config_dir: Path,
    run_id: str,
    metric_key: str,
    metric_value: float,
    commit_ref: str,
    timestamp_utc: str,
) -> Path:
    """Copy source config into tracked kept-configs directory."""

    run_dir = kept_config_dir / _safe_token(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    metric_token = _safe_token(f"{metric_key}-{metric_value:.12f}")
    filename = f"{_safe_token(timestamp_utc)}__{_safe_token(commit_ref)}__{metric_token}.yaml"
    target = run_dir / filename
    shutil.copy2(source_config, target)
    return target


def _promote_config(*, source_config: Path, promote_config_path: Path) -> None:
    """Overwrite canonical config path with source config content."""

    if source_config.resolve() == promote_config_path.resolve():
        return
    promote_config_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_config, promote_config_path)


def _compute_decision(
    *,
    status: str,
    metrics: RunMetrics | None,
    metric_key: str,
) -> tuple[str, float, float]:
    """Validate explicit status and derive metric/runtime values from run log."""

    normalized_status = str(status).strip()
    if normalized_status not in {"keep", "discard", "crash"}:
        raise ValueError(f"Unsupported --status value: {status!r}")

    if metrics is None:
        if normalized_status == "crash":
            return normalized_status, 0.0, 0.0
        raise ValueError(
            "AUTORESEARCH_METRIC is missing in run log. "
            "Use --status crash when run produced no metrics."
        )

    if metric_key not in metrics.values and normalized_status != "crash":
        raise ValueError(
            f"Metric key {metric_key!r} is missing in AUTORESEARCH_METRIC payload."
        )

    metric_value = float(metrics.values.get(metric_key, 0.0))
    runtime_sec = float(metrics.values.get("runtime_sec", 0.0))
    return normalized_status, metric_value, runtime_sec


def _build_decision_row(
    *,
    timestamp_utc: str,
    run_id: str,
    commit_ref: str,
    status: str,
    metric_key: str,
    metric_value: float,
    runtime_sec: float,
    metrics: RunMetrics | None,
    config_path: Path,
    config_sha256: str,
    config_snapshot_path: str,
    promoted_config_path: str,
    description: str,
) -> dict[str, str]:
    """Build one TSV history row payload."""

    metrics_payload = metrics.values if metrics is not None else {}
    return {
        "timestamp_utc": timestamp_utc,
        "run_id": run_id,
        "commit": commit_ref,
        "status": status,
        "metric_key": metric_key,
        "metric_value": f"{metric_value:.12f}",
        "runtime_sec": f"{runtime_sec:.3f}",
        "metrics_json": json.dumps(metrics_payload, ensure_ascii=True, sort_keys=True),
        "config_path": str(config_path),
        "config_sha256": config_sha256,
        "config_snapshot_path": config_snapshot_path,
        "promoted_config_path": promoted_config_path,
        "description": description,
    }


def _resolve_run_state(
    *,
    state_payload: dict[str, Any],
    run_id: str,
) -> dict[str, Any]:
    """Resolve per-run state container from global keep-state payload."""

    runs = state_payload.get("runs")
    if not isinstance(runs, dict):
        runs = {}
        state_payload["runs"] = runs
    run_state = runs.get(run_id)
    if not isinstance(run_state, dict):
        run_state = {}
        runs[run_id] = run_state
    return run_state


def _update_run_state(
    *,
    run_state: dict[str, Any],
    run_id: str,
    metric_key: str,
    keep_ref: str,
    metric_value: float,
    timestamp_utc: str,
    config_snapshot_path: str,
    config_sha256: str,
) -> None:
    """Update keep-state for one run id after a keep decision."""

    run_state["run_id"] = run_id
    run_state["metric_key"] = metric_key
    run_state["keep_ref"] = keep_ref
    run_state["best_metric"] = float(metric_value)
    run_state["best_config_snapshot_path"] = config_snapshot_path
    run_state["best_config_sha256"] = config_sha256
    run_state["updated_at_utc"] = timestamp_utc


def _update_last_decision(
    *,
    run_state: dict[str, Any],
    status: str,
    metric_key: str,
    metric_value: float,
    runtime_sec: float,
    timestamp_utc: str,
) -> None:
    """Store last agent decision metadata regardless of keep/discard/crash."""

    run_state["last_status"] = status
    run_state["last_metric_key"] = metric_key
    run_state["last_metric_value"] = float(metric_value)
    run_state["last_runtime_sec"] = float(runtime_sec)
    run_state["last_updated_at_utc"] = timestamp_utc


def main() -> int:
    """Persist one explicit keep/discard/crash decision."""

    args = _build_parser().parse_args()
    timestamp_utc = _utc_now_iso()

    run_id = str(args.run_id).strip()
    requested_status = str(args.status).strip()
    metric_key = str(args.metric_key).strip()
    if not run_id:
        raise ValueError("--run-id must be non-empty.")
    if not metric_key:
        raise ValueError("--metric-key must be non-empty.")

    run_log_path = Path(args.run_log)
    config_path = Path(args.config_path)
    state_path = Path(args.state_path)
    history_path = Path(args.history_path)
    kept_config_dir = Path(args.kept_config_dir)
    promote_config_path = Path(args.promote_config_path) if str(args.promote_config_path).strip() else None
    description = str(args.description).strip()

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    metrics = _read_run_metrics(run_log_path)
    config_sha256 = _compute_sha256(config_path)
    commit_ref = _git_commit_ref()

    state_payload = _load_json(state_path)
    run_state = _resolve_run_state(state_payload=state_payload, run_id=run_id)

    status, metric_value, runtime_sec = _compute_decision(
        status=requested_status,
        metrics=metrics,
        metric_key=metric_key,
    )

    keep_ref = str(run_state.get("keep_ref", ""))
    config_snapshot_path = ""
    promoted_config = ""
    if status == "keep":
        snapshot_path = _copy_config_snapshot(
            source_config=config_path,
            kept_config_dir=kept_config_dir,
            run_id=run_id,
            metric_key=metric_key,
            metric_value=metric_value,
            commit_ref=commit_ref,
            timestamp_utc=timestamp_utc,
        )
        config_snapshot_path = str(snapshot_path)
        explicit_keep_ref = str(args.keep_ref).strip()
        keep_ref = explicit_keep_ref or commit_ref
        _update_run_state(
            run_state=run_state,
            run_id=run_id,
            metric_key=metric_key,
            keep_ref=keep_ref,
            metric_value=metric_value,
            timestamp_utc=timestamp_utc,
            config_snapshot_path=config_snapshot_path,
            config_sha256=config_sha256,
        )
        if promote_config_path is not None:
            _promote_config(source_config=config_path, promote_config_path=promote_config_path)
            promoted_config = str(promote_config_path)

    _update_last_decision(
        run_state=run_state,
        status=status,
        metric_key=metric_key,
        metric_value=metric_value,
        runtime_sec=runtime_sec,
        timestamp_utc=timestamp_utc,
    )

    _write_json(state_path, state_payload)

    row = _build_decision_row(
        timestamp_utc=timestamp_utc,
        run_id=run_id,
        commit_ref=commit_ref,
        status=status,
        metric_key=metric_key,
        metric_value=metric_value,
        runtime_sec=runtime_sec,
        metrics=metrics,
        config_path=config_path,
        config_sha256=config_sha256,
        config_snapshot_path=config_snapshot_path,
        promoted_config_path=promoted_config,
        description=description,
    )
    _append_history_row(history_path, row)

    decision = RunDecision(
        status=status,
        metric_key=metric_key,
        metric_value=metric_value,
        runtime_sec=runtime_sec,
        keep_ref=keep_ref,
        config_snapshot_path=config_snapshot_path,
        promoted_config_path=promoted_config,
    )
    print(f"run_id={run_id}")
    print(f"status={decision.status}")
    print(f"metric_key={decision.metric_key}")
    print(f"metric_value={decision.metric_value:.12f}")
    print(f"runtime_sec={decision.runtime_sec:.3f}")
    print(f"keep_ref={decision.keep_ref}")
    print(f"config_sha256={config_sha256}")
    print(f"config_snapshot_path={decision.config_snapshot_path}")
    print(f"promoted_config_path={decision.promoted_config_path}")
    print(f"state_path={state_path}")
    print(f"history_path={history_path}")
    print(
        "AUTORESEARCH_KEEP "
        f"run_id={run_id} "
        f"status={decision.status} "
        f"metric_key={decision.metric_key} "
        f"metric_value={decision.metric_value:.12f} "
        f"keep_ref={decision.keep_ref} "
        f"config_sha256={config_sha256} "
        f"config_snapshot_path={decision.config_snapshot_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
