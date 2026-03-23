# [SCRIPT-HARDENING] [operator-scripts]

## Metadata + Exact Request
- Logged at: 23-03-2026 11:21
- Agent identity: Codex
- Task: SCRIPT-HARDENING
- Branch / worktree: main / /home/xeliaray/Projects/Agentic-RAG-Challenge
- Scope: Harden numbered operator scripts `00-07` so they use config-aware paths, expose honest dry-run or preflight flows, and validate outputs more truthfully.
- Exact user request or delegated objective:
  > Review the other scripts too because they are probably weak, then implement the hardening plan.

## Task Setup
- Context used: `scripts/about_directory.md`, all numbered shell scripts, `src/main.py`, `src/submission/sync.py`, current `.venv`, current Hugging Face cache, and operator workflow expectations established by prior env/model work.
- Constraints: Do not touch Memory Bank files; preserve backward-compatible manual usage where practical; avoid expensive mutating pipeline runs during verification; keep model IDs and product CLI semantics stable unless wrapper hardening truly requires changes.
- Planned approach: introduce a shared config-aware helper under `tools/`, rewire numbered scripts to use it, add dry-run/preflight or explicit context printing, then run targeted smoke checks.

## Implementation Log
1. Audited all numbered scripts against the real CLI contract in `src/main.py` and confirmed the main weaknesses were hardcoded paths, unconditional `--force`, missing preflight modes, and incomplete artifact validation.
2. Added `tools/operator_context.py` plus updated `tools/about_directory.md` so shell scripts can resolve phase-aware paths and provider-key presence from the active config/env.
3. Reworked `03_lint_and_test.sh` to check shell syntax and include `tools/` in Python lint/compile gates.
4. Reworked `04_parse_corpus.sh` and `05_build_indices.sh` to support named args, config-derived paths, `--dry-run`, optional `--force`, and more truthful artifact validation.
5. Reworked `06_build_submission.sh` to support `--preflight`, provider-key checks, config-derived defaults, and validation of `trace_manifest.json` plus `traces/`.
6. Reworked `07_validate_submission.sh` to expose `--questions-path`, `--documents-dir`, and `--output-path`, while always printing the resolved validation context.
7. Strengthened `00_check_env.sh` and `01_install_deps.sh` with additional Python runtime/model-cache and Hugging Face CLI checks; updated `scripts/about_directory.md` to match the new operator flow.

## Verification
- `bash -n scripts/00_check_env.sh scripts/01_install_deps.sh scripts/02_download_models.sh scripts/03_lint_and_test.sh scripts/04_parse_corpus.sh scripts/05_build_indices.sh scripts/06_build_submission.sh scripts/07_validate_submission.sh`
- `./.venv/bin/python tools/operator_context.py --config configs/baseline/v001/config.yaml --env-file .env --phase warmup --format json`
- `./scripts/00_check_env.sh`
- `./scripts/04_parse_corpus.sh --dry-run`
- `./scripts/05_build_indices.sh --dry-run`
- `./scripts/06_build_submission.sh --preflight`
- `./scripts/07_validate_submission.sh --help`
- `./scripts/07_validate_submission.sh`
- `./scripts/03_lint_and_test.sh`
- Result: operator interfaces and dry-run/preflight flows behave as intended. The updated quality gate surfaces an existing repo issue: 10 tests currently fail because OCR/Paddle runtime paths try to fetch official models in the installed GPU/Paddle environment.

## Issues / Resolutions
- Issue: Numbered scripts were duplicating `data/$PHASE/...` and artifact names instead of using config-derived truth.
- Resolution: introduced `tools/operator_context.py` and moved `04-07` onto config-aware resolution.
- Issue: `04/05` always ran expensive rebuilds with `--force`.
- Resolution: `--force` is now opt-in and both scripts expose `--dry-run`.
- Issue: `06` did not offer a safe preflight and ignored `trace_manifest.json` / `traces/`.
- Resolution: added `--preflight`, provider-key checks, and fuller output validation.
- Issue: `07` could validate a submission against implicit phase-local defaults without making that context explicit.
- Resolution: the script now exposes the full context and passes it explicitly to the CLI.
- Issue: The new `03` quality gate fails because the current repo test suite is not green with installed Paddle GPU/OCR runtime.
- Resolution: kept the stricter gate and recorded the failure as an existing operational risk rather than hiding it behind weaker script behavior.

## Artifacts
- Files touched: `scripts/00_check_env.sh`, `scripts/01_install_deps.sh`, `scripts/03_lint_and_test.sh`, `scripts/04_parse_corpus.sh`, `scripts/05_build_indices.sh`, `scripts/06_build_submission.sh`, `scripts/07_validate_submission.sh`, `scripts/about_directory.md`, `tools/operator_context.py`, `tools/about_directory.md`
- Reports, plots, logs, or other evidence: this activity log
- Verification artifacts: shell syntax pass, operator-context JSON output, dry-run/preflight outputs, explicit validation failure for missing submission, and the full failing pytest summary from `03_lint_and_test.sh`

## Result / Conclusions (Exact Answer to User)
> The numbered operator scripts are now substantially stronger: they resolve config-aware paths instead of hardcoding `data/$PHASE/...`, expose honest dry-run or preflight modes, and validate outputs more completely. The remaining issue surfaced by the new quality gate is not shell-wrapper weakness but an existing Paddle/OCR-related test instability in the repository when the GPU/Paddle runtime is installed.
