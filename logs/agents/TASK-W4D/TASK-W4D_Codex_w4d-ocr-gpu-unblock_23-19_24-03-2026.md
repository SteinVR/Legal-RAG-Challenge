# TASK-W4D w4d-ocr-gpu-unblock

## Metadata + Exact Request
- Logged at: 24-03-2026 23:19
- Agent identity: Codex
- Task: TASK-W4D
- Branch / worktree: `wave/TASK-W4D` / `/home/xeliaray/Projects/Agentic-RAG-Challenge/.apm/worktrees/TASK-W4D`
- Scope: Unblock OCR as a hard W4D dependency, require real GPU execution, and close the final quality gate.
- Exact user request or delegated objective:
  > Implement the plan and bring W4D to a working state, including the OCR blocker; OCR must run on GPU and the existing shared `.venv` must be preserved without redownloading heavy NVIDIA or Paddle packages.

## Task Setup
- Context used:
  - Existing W4D implementation and prior quality-gate evidence already present in the task worktree.
  - Shared `.venv` already contained `paddlepaddle-gpu`, `paddleocr`, `paddlex`, and cached NVIDIA packages.
  - Local PaddleX OCR model cache already existed under `~/.paddlex/official_models`.
- Constraints:
  - Do not reinstall or redownload heavy `nvidia-*` / Paddle packages.
  - OCR steady-state must be GPU-first; silent CPU fallback is not acceptable as normal operation.
  - Keep Memory Bank untouched.
- Planned approach:
  - Fix host GPU visibility first.
  - Harden OCR runtime/config in repo against current GPU/Paddle model-cache reality.
  - Verify with focused tests, live GPU OCR smoke, full suite, then reviewer-based quality gate.

## Implementation Log
1. Diagnosed the real blocker as host/runtime visibility rather than missing Python packages: kernel modules were loaded but `/dev/nvidia*` nodes were absent, so GPU-enabled Python runtimes could not see CUDA devices inside the working environment.
2. Restored host GPU visibility with `nvidia-modprobe`, then verified outside sandbox that `nvidia-smi`, `torch.cuda.is_available()`, and `paddle.device.cuda.device_count()` all reported a working GPU (`gpu:0`).
3. Added GPU-oriented OCR runtime configuration fields to [config.py](/home/xeliaray/Projects/Agentic-RAG-Challenge/.apm/worktrees/TASK-W4D/src/common/config.py) and corresponding env overrides:
   - `ocr_device`
   - `ocr_enable_hpi`
   - `ocr_enable_mkldnn`
   - `ocr_cpu_threads`
   - `ocr_model_root_dir`
   - `ocr_text_detection_model_dir`
   - `ocr_text_recognition_model_dir`
4. Hardened [ocr_engine.py](/home/xeliaray/Projects/Agentic-RAG-Challenge/.apm/worktrees/TASK-W4D/src/ingestion/ocr_engine.py):
   - fail fast when GPU OCR is requested but no CUDA devices are visible
   - set `PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK` before importing `paddleocr`
   - resolve local cached OCR model directories
   - resolve actual model names from cached model metadata and pass both `*_model_name` and `*_model_dir` into `PaddleOCR`
   - normalize init/predict runtime failures into `OcrUnavailableError`
5. Added and extended OCR/config coverage in:
   - [test_config.py](/home/xeliaray/Projects/Agentic-RAG-Challenge/.apm/worktrees/TASK-W4D/tests/test_config.py)
   - [test_ingestion_ocr_engine.py](/home/xeliaray/Projects/Agentic-RAG-Challenge/.apm/worktrees/TASK-W4D/tests/test_ingestion_ocr_engine.py)
   - [test_ingestion_pdf_parser.py](/home/xeliaray/Projects/Agentic-RAG-Challenge/.apm/worktrees/TASK-W4D/tests/test_ingestion_pdf_parser.py)
6. Ran a live out-of-sandbox smoke using `parse_pdf_document(..., ocr_engine=None)` on a temporary rasterized PDF and fixed the remaining real runtime defect: PaddleOCR initially rejected the cached recognition model with `Model name mismatch`, which was resolved by explicit model-name wiring from cache metadata.
7. Reused the existing W4D quality-gate subagents:
   - simplifier applied one low-risk cleanup to OCR env override handling in `config.py`
   - reviewer re-checked the final OCR/GPU delta and returned `APPROVE` with no `P0/P1/P2`

## Verification
- `PYTHONPATH=. .venv/bin/pytest -q tests/test_ingestion_ocr_engine.py tests/test_ingestion_pdf_parser.py tests/test_ingestion_service.py`
- `PYTHONPATH=. .venv/bin/ruff check src tests`
- `PYTHONPATH=. .venv/bin/pytest -q`
- Live out-of-sandbox GPU OCR smoke:
  - `paddle_compiled_with_cuda=True`
  - `paddle_device=gpu:0`
  - `paddle_cuda_device_count=1`
  - `parse_pdf_document` on a rasterized PDF returned `source_mode=ocr`, `triage=scan`, non-empty OCR text
- Quality gate reviewer result:
  - `P0`: none
  - `P1`: none
  - `P2`: none
  - verdict: `APPROVE`

## Issues / Resolutions
- Issue: Host GPU was effectively unavailable despite installed CUDA/Paddle packages.
  - Resolution: restored NVIDIA device-node visibility and verified GPU availability outside sandbox.
- Issue: PaddleOCR runtime failed against the cached English recognition model with `Model name mismatch`.
  - Resolution: derive actual model names from cached model metadata and pass explicit `text_detection_model_name` / `text_recognition_model_name` alongside local directories.
- Issue: `paddleocr` attempted hoster connectivity checks even though models were local.
  - Resolution: set `PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK` before importing `paddleocr`.
- Residual warnings:
  - `requests` dependency version warning from installed environment
  - sandboxed tests still emit Paddle CPU fallback warnings because GPU visibility differs inside sandbox
  - neither warning blocks the verified out-of-sandbox GPU OCR path or the green full suite

## Artifacts
- Files touched:
  - [config.py](/home/xeliaray/Projects/Agentic-RAG-Challenge/.apm/worktrees/TASK-W4D/src/common/config.py)
  - [ocr_engine.py](/home/xeliaray/Projects/Agentic-RAG-Challenge/.apm/worktrees/TASK-W4D/src/ingestion/ocr_engine.py)
  - [test_config.py](/home/xeliaray/Projects/Agentic-RAG-Challenge/.apm/worktrees/TASK-W4D/tests/test_config.py)
  - [test_ingestion_ocr_engine.py](/home/xeliaray/Projects/Agentic-RAG-Challenge/.apm/worktrees/TASK-W4D/tests/test_ingestion_ocr_engine.py)
  - [test_ingestion_pdf_parser.py](/home/xeliaray/Projects/Agentic-RAG-Challenge/.apm/worktrees/TASK-W4D/tests/test_ingestion_pdf_parser.py)
- Related evidence:
  - [TASK-W4D_Codex_w4d-ocr-followup-simplification_23-17_24-03-2026.md](/home/xeliaray/Projects/Agentic-RAG-Challenge/.apm/worktrees/TASK-W4D/logs/agents/TASK-W4D/TASK-W4D_Codex_w4d-ocr-followup-simplification_23-17_24-03-2026.md)
  - prior W4D integration and review logs already stored in the same task log directory
- Verification artifacts:
  - full suite result: `220 passed`
  - reviewer verdict: `APPROVE`

## Result / Conclusions (Exact Answer to User)
> W4D is now in a working state, including OCR as a real GPU dependency. The shared `.venv` was preserved, OCR runs against the existing cached Paddle models on `gpu:0`, the full test suite is green (`220 passed`), and the final reviewer returned `APPROVE` with no `P0/P1/P2`.
