# TASK-W3A review-fixes-4

## Metadata + Exact Request
- Logged at: 21-03-2026 23:00
- Agent identity: Leo
- Task: TASK-W3A
- Branch / worktree: `.apm/worktrees/TASK-W3A`
- Scope: Fix the remaining P1 heading-parser bug for merged heading+body paragraphs and re-run the exact requested verification commands.
- Exact user request or delegated objective:
  > Fix over-greedy heading detection for shapes like `Section 9 Duties The entity must maintain records.`, add a regression, and rerun the two pytest commands plus `ruff` with `PYTHONPATH=$PWD`.

## Task Setup
- Context used:
  - current `src/indexing/service.py`
  - current `tests/test_indexing_service.py`
- Constraints:
  - W3A worktree-only ownership
  - no Memory Bank changes
  - no `main.py` edits
  - verify with the exact provided commands
- Planned approach:
  - split heading-prefixed paragraphs into heading label plus body remainder
  - reuse that split for both heading extraction and content-paragraph preservation
  - add an exact regression for the reproduced paragraph shape

## Implementation Log
1. Replaced the over-greedy whole-paragraph heading detection with a shared heading/body splitter for `Part`, `Article`, and `Section` paragraphs.
2. Added body-start heuristics so merged heading+body paragraphs preserve the first real provision sentence as content instead of absorbing it into the heading label.
3. Updated content-paragraph extraction to keep the body remainder from split heading paragraphs.
4. Added a regression covering `Section 9 Duties The entity must maintain records.\n\nAdditional rules apply.` and verified that clause/section content now starts at the provision text.

## Verification
- `env PYTHONPATH=$PWD /home/xeliaray/Projects/Agentic-RAG-Challenge/.venv/bin/python -m pytest -q tests/test_indexing_service.py`
- Result: `17 passed in 0.69s`
- `env PYTHONPATH=$PWD /home/xeliaray/Projects/Agentic-RAG-Challenge/.venv/bin/python -m pytest -q tests/test_indexing_service.py tests/test_config.py tests/test_ingestion_corpus_builder.py`
- Result: `26 passed in 0.73s`
- `env PYTHONPATH=$PWD /home/xeliaray/Projects/Agentic-RAG-Challenge/.venv/bin/python -m ruff check src/indexing tests/test_indexing_service.py`
- Result: `All checks passed!`

## Issues / Resolutions
- Issue: heading detection treated merged heading+body paragraphs as pure headings, which dropped the first real provision sentence from chunking.
- Resolution: introduced heading/body splitting and reused it consistently across heading extraction and content extraction.
- Residual risk: the body-start heuristic is intentionally conservative and tuned to common legal prose starts; rarer heading/body merge shapes may need additional cues later.

## Artifacts
- Files touched:
  - `src/indexing/service.py`
  - `tests/test_indexing_service.py`
  - `logs/agents/TASK-W3A/TASK-W3A_Leo_review-fixes-4_23-00_21-03-2026.md`
- Verification artifacts:
  - exact command results recorded above

## Result / Conclusions (Exact Answer to User)
> TASK-W3A now preserves provision text in merged heading+body paragraphs, the requested regression is in place, and the exact pytest/ruff commands pass with `PYTHONPATH=$PWD`.
