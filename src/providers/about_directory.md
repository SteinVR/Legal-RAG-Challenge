# About This Directory
Purpose: Provider abstraction for model-backed answer solving.
Contains: The provider protocol plus the concrete Codex-backed implementation for grounded free-text generation, W4B structured answering, and W4C structured sidecar generation.
Start Here: `base.py` for the contract, then `codex_provider.py` for the actual `/responses` integrations.
Key Files/Dirs: `base.py`, `codex_provider.py`.
Notes: This directory covers model invocation only; retrieval, deterministic guardrails, and final answer shaping stay outside in `src/answering/` and `src/retrieval/`.
