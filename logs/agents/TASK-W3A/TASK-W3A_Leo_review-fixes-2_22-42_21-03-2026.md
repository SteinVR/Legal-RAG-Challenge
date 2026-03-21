# TASK-W3A review-fixes-2

## Metadata + Exact Request
- Logged at: 21-03-2026 22:42
- Agent identity: Leo
- Task: TASK-W3A
- Branch / worktree: `.apm/worktrees/TASK-W3A`
- Scope: Apply the remaining quality-gate findings inside the W3A worktree and re-verify with `PYTHONPATH=$PWD`.
- Exact user request or delegated objective:
  > Preserve legal numbering in heading labels, validate `page_parent_map.json` during skip/reuse, and remove the fake section layer by making section chunks truthful or dropping them.

## Task Setup
- Context used:
  - current `src/indexing/service.py`
  - current `tests/test_indexing_service.py`
- Constraints:
  - worktree-only W3A ownership
  - no git ops
  - no Memory Bank updates
  - no `main.py` edits
- Planned approach:
  - fix heading extraction to preserve identifiers
  - harden skip validation against corrupt or mismatched page-parent maps
  - replace duplicate page-as-section chunks with real section spans

## Implementation Log
1. Updated heading extraction to preserve full legal labels such as `Part 2 TERMINATION` and `Section 4 Notice`.
2. Refactored section chunking so `section` chunks are derived from contiguous heading spans and section body text, rather than duplicating full-page chunks.
3. Hardened skip/reuse validation to parse `page_parent_map.json`, reject corrupt or unreadable payloads, and require entry count equality with `chunk_count`.
4. Added regression coverage for:
   - unreadable `page_parent_map.json`
   - page-parent-map entry-count mismatch
   - numbered heading preservation
   - real section-span chunk semantics

## Verification
- `PYTHONPATH=$PWD /home/xeliaray/Projects/Agentic-RAG-Challenge/.venv/bin/pytest tests/test_indexing_service.py`
- Result: `14 passed`
- `PYTHONPATH=$PWD /home/xeliaray/Projects/Agentic-RAG-Challenge/.venv/bin/pytest tests/test_indexing_service.py tests/test_config.py tests/test_ingestion_corpus_builder.py`
- Result: `23 passed`

## Issues / Resolutions
- Issue: skip validation was never succeeding because the page-parent-map helper was called as an instance method even though it is a module function.
- Resolution: fixed the call site and validated map readability plus entry count before allowing reuse.
- Issue: heading parsing still stripped numbering because the regex captured only the trailing title text.
- Resolution: captured full heading lines and normalized only the keyword casing.
- Residual risk: section spans are now truthful and non-duplicate for headed content, but headingless documents intentionally do not receive synthetic `section` chunks.

## Artifacts
- Files touched:
  - `src/indexing/service.py`
  - `tests/test_indexing_service.py`
  - `logs/agents/TASK-W3A/TASK-W3A_Leo_review-fixes-2_22-42_21-03-2026.md`
- Verification artifacts:
  - passing worktree-local pytest runs recorded above

## Result / Conclusions (Exact Answer to User)
> TASK-W3A now preserves numbered legal headings, validates page-parent maps before reuse, emits truthful section chunks instead of page duplicates, and passes the requested worktree-local verification.
