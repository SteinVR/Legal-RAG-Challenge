# DOCS-NAV about-directory-lifecycle

## Metadata + Exact Request
- Logged at: 22-03-2026 23:44
- Agent identity: Codex
- Task: DOCS-NAV
- Branch / worktree: current workspace root at `/home/xeliaray/Projects/Agentic-RAG-Challenge`
- Scope: strengthen the repository instruction entrypoints so `about_directory.md` must be maintained when directory structure changes
- Exact user request or delegated objective:
  > Add an instruction, in the optimal place, that `about_directory.md` files must be updated or created when changes and new additions happen, otherwise the mechanism is broken.

## Task Setup
- Context used:
  - root `AGENTS.md`
  - root `CLAUDE.md`
  - local `tests/AGENTS.md` and `logs/AGENTS.md` to check whether root-level placement was sufficient
- Constraints:
  - keep the rule repo-wide and low-drift
  - cover both creation and update cases
  - avoid requiring guides for hidden, tooling, cache, raw artifact, or run-leaf directories
- Planned approach:
  - extend the root `Directory navigation` policy in `AGENTS.md`
  - mirror the same lifecycle rule in `CLAUDE.md`
  - leave local specialized `AGENTS.md` files unchanged unless a conflict appears

## Implementation Log
1. Re-read the root and local instruction files to verify where a global navigation-maintenance rule should live.
2. Added lifecycle bullets to `AGENTS.md` requiring `about_directory.md` creation for new stable first-party navigation directories and updates when maintained directories materially change.
3. Added the same lifecycle rule to `CLAUDE.md`, including the explicit exclusion for hidden/tooling, cache, raw artifact, and run-specific log leaves.

## Verification
- Re-read the modified `AGENTS.md` and `CLAUDE.md` after editing.
- Confirmed the wording now covers `read-first`, `create-on-new-directory`, `update-on-structural-change`, and `docs-defect` behavior.

## Issues / Resolutions
- The existing instruction only covered reading `about_directory.md`, not maintaining it.
- Resolved by turning the navigation rule into a lifecycle policy with explicit scope boundaries.
- Local `tests/AGENTS.md` and `logs/AGENTS.md` could have been extra insertion points.
- Resolved by keeping the lifecycle rule centralized in the root entrypoint files to reduce duplication and drift.

## Artifacts
- Files touched:
  - `AGENTS.md`
  - `CLAUDE.md`
  - this activity log
- Reports, plots, logs, or other evidence:
  - `logs/agents/DOCS-NAV/DOCS-NAV_Codex_about-directory-lifecycle_23-44_22-03-2026.md`
- Verification artifacts:
  - post-edit readback of the changed instruction blocks

## Result / Conclusions (Exact Answer to User)
> Added a repo-wide lifecycle instruction to `AGENTS.md` and `CLAUDE.md` requiring `about_directory.md` files to be created for new stable first-party navigation directories and updated whenever those directories materially change.
