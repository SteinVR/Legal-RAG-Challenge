# TASK-W4C opendataloader-runtime-script

## Metadata + Exact Request
- Logged at: 24-03-2026 18:07
- Agent identity: Codex
- Task: TASK-W4C
- Branch / worktree: `wave/TASK-W4C` / `/home/xeliaray/Projects/Agentic-RAG-Challenge/.apm/worktrees/TASK-W4C`
- Scope: Prepare a manual operator script for vendored `opendataloader-pdf` runtime installation.
- Exact user request or delegated objective:
  > Тогда подготовь скрипт по установке, я его лично запущу

## Task Setup
- Context used:
  - `scripts/about_directory.md`
  - `scripts/01_install_deps.sh`
  - vendored `external/opendataloader-pdf` Python runner/build files
- Constraints:
  - prepare the script only; do not run system installation from the agent session
  - keep it operator-facing and reproducible
- Planned approach:
  - add a dedicated install script under `scripts/`
  - cover package-manager detection, JDK/Maven install, vendored JAR build, Python wrapper install, and verification

## Implementation Log
1. Inspected the existing operator script layout and confirmed `scripts/` is the correct location.
2. Read vendored `opendataloader-pdf` runner/build files to verify that the Python wrapper expects a bundled JAR produced by `mvn package`.
3. Added `scripts/01b_install_opendataloader_runtime.sh` with manual flags for hybrid/runtime bootstrap and `--skip-system-packages`.
4. Re-reviewed the task and architecture context: for `TASK-W4C`, hybrid mode is the required default structural path for born-digital/layout-complex documents when the backend is reachable, so the install script was switched to install hybrid extras by default and expose `--without-hybrid` as the opt-out.
5. Updated `scripts/about_directory.md` so the new bootstrap path is discoverable.
6. Verified the user-run installation and found one real runtime caveat: the vendored CLI needs `-Djava.awt.headless=true` on this host for actual parses, otherwise PDFBox fails against X11.
7. Updated the script verification path to perform a real headless smoke parse, not just import/CLI checks.
8. Marked the new script executable and syntax-checked it with `bash -n`.

## Verification
- `bash -n scripts/01b_install_opendataloader_runtime.sh`
- Result: syntax OK
- `chmod +x scripts/01b_install_opendataloader_runtime.sh`
- Result: executable bit set

## Issues / Resolutions
- The session still cannot validate real system package installation because that requires user-run elevated commands.
- Resolved by preparing an operator-run script instead of attempting installation from the agent session.

## Artifacts
- Files touched:
  - `scripts/01b_install_opendataloader_runtime.sh`
  - `scripts/about_directory.md`
- Verification artifacts:
  - successful `bash -n` syntax check

## Result / Conclusions (Exact Answer to User)
> Prepared a manual install script at `scripts/01b_install_opendataloader_runtime.sh`. It installs Java/Maven for the detected package manager, builds the vendored `opendataloader-pdf` JAR, installs the Python wrapper into `.venv`, and verifies the resulting runtime without requiring the agent to run the installation itself.
