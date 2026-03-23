# [ENV-MODEL-GPU-RUNTIME] qwen-gpu-runtime

## Metadata + Exact Request
- Logged at: [23-03-2026 11:45]
- Agent identity: [Codex]
- Task: [ENV-MODEL-GPU-RUNTIME]
- Branch / worktree: [main repo workspace]
- Scope: [restore GPU visibility for Qwen embedder/reranker and harden operator diagnostics]
- Exact user request or delegated objective:
  > Проверить, загружены ли модели Embedding и Reranker, готовы ли к использованию, работают ли на GPU; если нет, загрузить и починить GPU-path.

## Task Setup
- Context used: existing `.venv`, `scripts/00_check_env.sh`, `scripts/02_download_models.sh`, HF cache under `/home/xeliaray/.cache/huggingface/hub`, host NVIDIA stack on CachyOS.
- Constraints: avoid re-downloading NVIDIA/CUDA packages; keep using cached model artifacts; prefer operator-facing scripts.
- Planned approach: verify cache and runtime, isolate GPU blocker, add an explicit repair path, then validate embedder and reranker on GPU.

## Implementation Log
1. Verified both model caches exist locally and that `./scripts/02_download_models.sh --verify` passes CPU smoke while failing only on `torch.cuda.is_available() == False`.
2. Diagnosed host stack: kernel modules and PCI binding were healthy, but `/dev/nvidia*` device nodes were missing; `nvidia-smi` failed until `nvidia-modprobe` recreated the nodes.
3. Hardened `scripts/00_check_env.sh` to report kernel-visible GPUs, missing NVIDIA device nodes, `torch`/`paddle` state, and the exact recovery action.
4. Added `scripts/00_repair_gpu_runtime.sh` as the operator-facing repair path that runs `nvidia-modprobe`, verifies `/dev/nvidia*`, shows `nvidia-smi`, and confirms CUDA visibility from `.venv`.
5. Updated `scripts/about_directory.md` to include the new GPU runtime recovery workflow.

## Verification
- `bash -n scripts/00_check_env.sh scripts/00_repair_gpu_runtime.sh`
- `./scripts/00_repair_gpu_runtime.sh` outside sandbox: passed
- `./scripts/00_check_env.sh` outside sandbox after repair: GPU visible, model cache present
- `./scripts/02_download_models.sh --verify` outside sandbox: passed CPU and GPU smoke checks for both models

## Issues / Resolutions
- Issue: host kernel saw the RTX 4060, but `/dev/nvidia*` was absent, so `nvidia-smi`, `torch`, and `paddle` fell back to CPU.
- Resolution: `nvidia-modprobe` recreated the device nodes without reinstalling any NVIDIA/CUDA packages; new repair script codifies that path.
- Residual risk: loading `Qwen/Qwen3-Reranker-0.6B` still reports `score.weight` as `MISSING`, so GPU execution is verified but reranker quality semantics remain unvalidated.
- Residual nuance: Codex sandbox hides GPU devices, so non-escalated checks inside the tool can still report CPU-only even after the real host is fixed.

## Artifacts
- Files touched: `scripts/00_check_env.sh`, `scripts/00_repair_gpu_runtime.sh`, `scripts/about_directory.md`
- Reports, plots, logs, or other evidence: this activity log
- Verification artifacts: successful outside-sandbox runs of `00_repair_gpu_runtime.sh`, `00_check_env.sh`, and `02_download_models.sh --verify`

## Result / Conclusions (Exact Answer to User)
> Обе модели уже загружены, доступны из HF cache и после восстановления `/dev/nvidia*` реально проходят GPU smoke-check. Для повторного восстановления после ребута теперь есть `./scripts/00_repair_gpu_runtime.sh`; после него можно запускать `./scripts/02_download_models.sh --verify`.
