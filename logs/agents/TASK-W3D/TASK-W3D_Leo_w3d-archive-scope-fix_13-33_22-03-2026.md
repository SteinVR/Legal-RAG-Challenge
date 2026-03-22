# TASK-W3D w3d-archive-scope-fix

## Metadata + Exact Request
- Logged at: 22-03-2026 13:33
- Agent identity: Leo
- Task: TASK-W3D
- Branch / worktree: TASK-W3D / /home/xeliaray/Projects/Agentic-RAG-Challenge/.apm/worktrees/TASK-W3D
- Scope: Fix root-workspace archive oversize blocker by making code archive scope strict and deterministic.
- Exact user request or delegated objective:
  > build-submission archives exceed 25MB in root workspace; make archive contents strict submission-safe for main workspace, preserve secret exclusion/outside-root safety/archive-size gate, add regression coverage, rerun requested root-style test commands.

## Task Setup
- Context used:
  - root blocker report
  - `src/submission/packager.py`
  - `src/submission/pipeline.py`
  - `tests/test_submission_pipeline.py`
- Constraints:
  - No regression on existing gates and exclusions.
- Planned approach:
  - Add include-scope support to packager.
  - Make pipeline use strict deterministic archive include paths.
  - Add regression proving large non-shipping paths are excluded under include scope.

## Implementation Log
1. Extended packager API:
   - `SubmissionPackager.create_code_archive(..., include_paths=...)` now accepts explicit include scope.
   - Added include-path normalization and scoped archive candidate iteration.
2. Kept prior safeguards intact:
   - `.env` / `.env.*` secret exclusion still enforced.
   - outside-root symlink/target safety still enforced.
   - archive-size gate unchanged.
3. Updated pipeline to use strict deterministic archive scope (`src`, `configs`, `scripts`, `tools`, and minimal root metadata files).
4. Added regression test:
   - `test_code_archive_include_paths_keep_archive_under_limit_with_large_non_shipping_files`
   - validates that a >25MB non-shipping file outside include scope does not bloat archive.

## Verification
- Checks run:
  - `PYTHONPATH=. ./.venv/bin/ruff check src/submission/packager.py src/submission/pipeline.py tests/test_submission_pipeline.py`
  - `PYTHONPATH=. ./.venv/bin/python -m pytest -q tests/test_submission_pipeline.py tests/test_main.py`
  - `PYTHONPATH=. ./.venv/bin/python -m pytest -q`
- Result:
  - `ruff`: passed.
  - Requested subset: 29 passed.
  - Full suite: 180 passed.

## Issues / Resolutions
- Issue: broad recursive archive walk in main workspace included large non-shipping areas, causing >25MB archive failures.
- Resolution: strict deterministic include scope in pipeline archive call, with packager support for include-scoped collection.

## Artifacts
- Files touched:
  - src/submission/packager.py
  - src/submission/pipeline.py
  - tests/test_submission_pipeline.py
- Reports/logs:
  - This activity log.
- Verification artifacts:
  - Green command outputs listed above.

## Result / Conclusions (Exact Answer to User)
> Root-workspace archive oversize blocker is fixed: build-submission now packages a strict code scope, preserving secret/outside-root safety and archive-size gate, with regression coverage added and requested verification green.
