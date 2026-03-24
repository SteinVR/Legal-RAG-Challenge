# About This Directory
Purpose: Provider abstraction for model-backed answer solving.
Contains: The provider protocol plus the concrete Codex-backed implementation for both legacy free-text generation and W4B structured solving across all answer types.
Start Here: `base.py` for the contract, then `codex_provider.py` for the actual HTTP integration.
Key Files/Dirs: `base.py`, `codex_provider.py`.
Notes: This directory covers model invocation only; retrieval, deterministic guardrails, and final answer shaping stay in `src/answering/`.
