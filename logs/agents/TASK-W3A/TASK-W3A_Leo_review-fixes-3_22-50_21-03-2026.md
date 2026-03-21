# TASK-W3A review-fixes-3

## Metadata + Exact Request
- Logged at: 21-03-2026 22:50
- Agent identity: Leo
- Task: TASK-W3A
- Branch / worktree: `.apm/worktrees/TASK-W3A`
- Scope: Apply the remaining structure-preservation findings in the W3A worktree and re-verify with `PYTHONPATH=$PWD`.
- Exact user request or delegated objective:
  > Expand heading detection to article-based forms, support broader legal clause labels such as `(a)`, `(1)`, and `10A`, and preserve orphan lead-in paragraphs before numbered clauses.

## Task Setup
- Context used:
  - current `src/indexing/service.py`
  - current `tests/test_indexing_service.py`
- Constraints:
  - W3A worktree-only ownership
  - no Memory Bank updates
  - no `main.py` edits
  - verification must use worktree-local import resolution
- Planned approach:
  - extend heading parsing with an `ARTICLE` tier
  - widen clause-label parsing to common legal forms while preserving real labels
  - synthesize a lead-in clause when unlabeled text precedes labeled clauses

## Implementation Log
1. Added article-based heading detection and carryover, preserving labels such as `Article 3 GENERAL OBLIGATIONS`.
2. Expanded clause-label parsing to preserve real labels for forms including `(a)`, `(1)`, and `10A`.
3. Updated clause-source extraction so orphan lead-in paragraphs before numbered clauses are preserved as a synthetic first clause (`lead-in`) instead of being dropped.
4. Added regressions covering:
   - article-based pages with preserved real clause labels
   - orphan lead-in paragraphs before labeled clauses

## Verification
- `PYTHONPATH=$PWD /home/xeliaray/Projects/Agentic-RAG-Challenge/.venv/bin/pytest tests/test_indexing_service.py`
- Result: `16 passed`
- `PYTHONPATH=$PWD /home/xeliaray/Projects/Agentic-RAG-Challenge/.venv/bin/pytest tests/test_indexing_service.py tests/test_config.py tests/test_ingestion_corpus_builder.py`
- Result: `25 passed`

## Issues / Resolutions
- Issue: the prior parser only recognized `Part` and `Section` headings and only matched plain numeric clause labels.
- Resolution: extended heading and clause parsing to legal shapes that the quality gate flagged explicitly.
- Residual risk: the parser now covers the requested common forms, but more exotic legal numbering systems such as nested roman-numeral subclauses are not yet explicitly normalized.

## Artifacts
- Files touched:
  - `src/indexing/service.py`
  - `tests/test_indexing_service.py`
  - `logs/agents/TASK-W3A/TASK-W3A_Leo_review-fixes-3_22-50_21-03-2026.md`
- Verification artifacts:
  - passing worktree-local pytest runs recorded above

## Result / Conclusions (Exact Answer to User)
> TASK-W3A now preserves article headings, broader real clause labels, and orphan lead-in text before labeled clauses, and the requested worktree-local verification passes.
