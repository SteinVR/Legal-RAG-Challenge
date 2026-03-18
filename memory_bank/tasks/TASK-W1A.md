# Task: TASK-W1A

## 1. Summary

**Title**: Workspace, config & corpus access  
**Description**: Set up runnable project skeleton: dependencies, config management, competition API client, download warm-up corpus and questions.  
**Status**: Planned
**Wave**: Wave 1 -- Foundation

## 2. Scope

- **In scope**:
  - pyproject.toml / requirements with pinned deps
  - src/ package structure with __init__.py
  - Config loader + baseline v001 config
  - Competition API client (download docs, questions, submit)
  - Download and store warm-up corpus (30 docs, 100 questions)
  - Phase isolation (warmup / final separate dirs)
  - .env for API key management
- **Out of scope**: ingestion, indexing, retrieval, answering logic
- **Dependencies**: competition API key (from user)

## 3. Implementation Plan


## 4. Working Notes

Competition API: `https://platform.agentic-challenge.ai/api/v1`
Auth: `X-API-Key` header.
Documents endpoint returns ZIP of PDFs; questions endpoint returns JSON array.

## 5. Outcome

**Result**: [Pending]  
**Next action**: implement in Wave 1 after confirmation
