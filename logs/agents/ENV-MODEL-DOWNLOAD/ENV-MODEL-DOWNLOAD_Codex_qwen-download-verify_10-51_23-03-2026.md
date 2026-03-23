# [ENV-MODEL-DOWNLOAD] [qwen-download-verify]

## Metadata + Exact Request
- Logged at: 23-03-2026 10:51
- Agent identity: Codex
- Task: ENV-MODEL-DOWNLOAD
- Branch / worktree: main / /home/xeliaray/Projects/Agentic-RAG-Challenge
- Scope: Replace the model helper with a human-run Hugging Face download workflow and a separate offline/GPU verification path for the embedder and reranker.
- Exact user request or delegated objective:
  > Solve the embedder/reranker model setup next, make sure the download script is actually workable, and then hand that script to the user so they can run it themselves and watch the download progress.

## Task Setup
- Context used: `scripts/02_download_models.sh`, `scripts/about_directory.md`, `src/indexing/service.py`, `src/retrieval/reranker.py`, current `.venv`, and the existing Hugging Face cache under `/home/xeliaray/.cache/huggingface/hub`.
- Constraints: Keep the operator-facing download path visible and manual; preserve the existing shared Hugging Face cache; do not change model IDs in runtime code; current host does not expose working CUDA to `torch`.
- Planned approach: Rewrite the helper as a progress-visible `hf download` wrapper, add `--verify` for offline cache validation plus GPU smoke tests, and prove behavior with dry-run/download-path checks and offline loads.

## Implementation Log
1. Inspected the current helper and runtime code. Confirmed that the embedder and reranker are hardcoded to `Qwen/Qwen3-Embedding-0.6B` and `Qwen/Qwen3-Reranker-0.6B`, and that the previous helper mixed downloading with immediate Python model instantiation.
2. Confirmed that both model repos already exist in the Hugging Face cache, and that they load successfully offline only when `HF_HUB_OFFLINE=1` is set.
3. Replaced `scripts/02_download_models.sh` with an operator-first script: default mode uses `.venv/bin/hf download` with visible progress, and `--verify` performs offline cache validation plus GPU smoke tests.
4. Updated `scripts/about_directory.md` so the scripts directory navigation reflects the new download/verify workflow.

## Verification
- `bash -n scripts/02_download_models.sh`
- `./scripts/02_download_models.sh --help`
- `./scripts/02_download_models.sh --verify`
- `./.venv/bin/hf download --dry-run Qwen/Qwen3-Embedding-0.6B`
- `./.venv/bin/hf download --dry-run Qwen/Qwen3-Reranker-0.6B`
- Result: `--verify` passed offline CPU validation for both models and then exited with code `2` because `torch.cuda.is_available()` is `False` on this host. Both `hf download --dry-run` checks succeeded with live Hub access and showed that only a few small files remain uncached.

## Issues / Resolutions
- Issue: The old helper was not a good operator script because it hid download progress inside Python model loads and `local_files_only=True` still triggered unexpected network lookups.
- Resolution: Moved the primary operator path to explicit `hf download`, which shows progress bars and uses the existing Hugging Face cache directly.
- Issue: Repo-ID based offline loads still attempted network access unless Hugging Face offline mode was forced.
- Resolution: `--verify` now exports `HF_HUB_OFFLINE=1` before loading either model.
- Issue: Current host still does not expose working CUDA to `torch`.
- Resolution: `--verify` now distinguishes “cache/model load OK” from “GPU runtime unavailable” and fails with an explicit message instead of an opaque traceback.

## Artifacts
- Files touched: `scripts/02_download_models.sh`, `scripts/about_directory.md`
- Reports, plots, logs, or other evidence: this activity log
- Verification artifacts: shell syntax check, script help output, live `hf download --dry-run` output for both model repos, offline CPU validation output, and explicit GPU-unavailable failure output from `--verify`

## Result / Conclusions (Exact Answer to User)
> The model helper now has the operator-facing shape you asked for: running `./scripts/02_download_models.sh` will show real Hugging Face download progress, while `./scripts/02_download_models.sh --verify` checks that both models load from cache offline and then enforces a GPU smoke test. On the current host, cache validation succeeds but GPU verification still fails because `torch` does not see CUDA.
