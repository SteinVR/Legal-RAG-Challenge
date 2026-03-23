# INGESTION-SYNTHESIS rename-docs

## Metadata + Exact Request
- Logged at: 23-03-2026 20:37
- Agent identity: Codex
- Task: INGESTION-SYNTHESIS
- Branch / worktree: `main`
- Scope: Remove naming ambiguity between the canonical unified architecture document and the archival note in `docs/addition/`.
- Exact user request or delegated objective:
  > ingestion_stack_synthesis.md никак не зависит от addition/ingestion_stack_synthesis.md? - он должен быть самостоятельным и исчерпывающим
  >
  > поменяй наименования, чтобы не путать

## Task Setup
- Context used:
  - current `docs/` navigation files;
  - the canonical architecture doc created in the previous pass;
  - the archival note under `docs/addition/`.
- Constraints:
  - keep the canonical document standalone and exhaustive;
  - remove filename ambiguity rather than explaining it away;
  - update navigation to match the new names.
- Planned approach:
  - rename the canonical file to a clearly authoritative architecture name;
  - rename the archival note to an explicit legacy name;
  - update all documentation pointers under `docs/`.

## Implementation Log
1. Searched all references to the previous `ingestion_stack_synthesis` names under `docs/` and the task log directory to identify the exact rename surface.
2. Renamed `docs/ingestion_stack_synthesis.md` to `docs/unified_document_processing_architecture.md` and updated its title to match the new canonical role.
3. Renamed `docs/addition/ingestion_stack_synthesis.md` to `docs/addition/legacy_ingestion_stack_note.md` and updated its pointer text so it clearly refers to the standalone canonical document.
4. Updated `docs/about_directory.md` and `docs/addition/about_directory.md` so navigation now points to the renamed canonical file and the renamed legacy note.

## Verification
- Ran repository-local search for old doc references under `docs/` and this task log area before the rename.
- Re-checked the renamed files and navigation files after the rename to confirm the new names are in place and the archival note no longer shares the canonical filename.

## Issues / Resolutions
- The previous naming scheme kept the canonical document and the archival note under the same basename, which made the relationship look less independent than intended.
- Resolved by assigning distinct names based on role: canonical architecture vs legacy note.

## Artifacts
- Files touched:
  - `docs/unified_document_processing_architecture.md`
  - `docs/about_directory.md`
  - `docs/addition/about_directory.md`
  - `docs/addition/legacy_ingestion_stack_note.md`
  - `logs/agents/INGESTION-SYNTHESIS/INGESTION-SYNTHESIS_Codex_rename-docs_20-37_23-03-2026.md`
- Verification artifacts:
  - local `rg` search results;
  - local file inspection after rename.

## Result / Conclusions (Exact Answer to User)
> The canonical document is now a standalone file named `docs/unified_document_processing_architecture.md`. The archival note has been renamed to `docs/addition/legacy_ingestion_stack_note.md`, and docs navigation was updated so the two roles are no longer easy to confuse.
