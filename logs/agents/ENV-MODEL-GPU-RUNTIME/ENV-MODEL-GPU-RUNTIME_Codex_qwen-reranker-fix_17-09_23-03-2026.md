# [ENV-MODEL-GPU-RUNTIME] qwen-reranker-fix

## Metadata + Exact Request
- Logged at: [23-03-2026 17:09]
- Agent identity: [Codex]
- Task: [ENV-MODEL-GPU-RUNTIME]
- Branch / worktree: [main repo workspace]
- Scope: [diagnose the Qwen reranker warning and correct reranker loading/scoring]
- Exact user request or delegated objective:
  > Проверить warning у `Qwen3-Reranker-0.6B`, понять, что он значит, и исправить загрузку/использование reranking, если оно неверное.

## Task Setup
- Context used: local HF snapshot for `Qwen/Qwen3-Reranker-0.6B`, current backend in `src/retrieval/reranker.py`, operator verification script, and retrieval unit tests.
- Constraints: keep offline/local-cache behavior, preserve GPU support, avoid unnecessary package or model re-downloads.
- Planned approach: inspect checkpoint metadata and official usage, compare with current code path, replace incorrect loading strategy, then re-verify on CPU and GPU.

## Implementation Log
1. Inspected the local reranker snapshot and confirmed `config.json` declares `architectures: ["Qwen3ForCausalLM"]`, while the code was loading `AutoModelForSequenceClassification`.
2. Confirmed the checkpoint lacks `score.weight` in `model.safetensors`, so the old warning meant Transformers was creating a fresh classification head that was never trained for this checkpoint.
3. Checked the official Hugging Face model card and aligned the backend with the documented inference path: load `AutoModelForCausalLM`, build the reranker prompt, and score the final-step `"yes"` vs `"no"` token probabilities.
4. Updated `src/retrieval/reranker.py` to use local snapshot resolution via `snapshot_download(..., local_files_only=True)`, preventing hidden HF network lookups during offline inference.
5. Updated `scripts/02_download_models.sh --verify` to exercise the real backend instead of a duplicated, incorrect classification-model smoke test.
6. Added a focused unit test in `tests/test_retrieval_components.py` covering the causal-LM yes/no scoring path and prompt formatting.

## Verification
- `./.venv/bin/python -m compileall src/retrieval/reranker.py tests/test_retrieval_components.py`
- `./.venv/bin/pytest tests/test_retrieval_components.py -q`
- `HF_HUB_OFFLINE=1 ./.venv/bin/python ... TransformersQwenRerankerBackend(device='cpu').score(...)`
- `./scripts/00_repair_gpu_runtime.sh`
- `./scripts/02_download_models.sh --verify` outside sandbox on GPU

## Issues / Resolutions
- Issue: `score.weight` appeared as `MISSING` because the code was loading a causal-LM checkpoint as a sequence-classification model.
- Resolution: switched to the official Qwen reranker inference path based on final-token `"yes"`/`"no"` probabilities from `AutoModelForCausalLM`.
- Issue: tokenizer loading by repo ID could still attempt hidden Hub requests even with `local_files_only=True`.
- Resolution: backend now resolves the local snapshot path first and passes that filesystem path to Transformers.
- Residual nuance: the smoke example currently saturates to a score near `1.0`, which is plausible for an obviously relevant document; ranking correctness now depends on actual corpus/query difficulty rather than an accidental random head.

## Artifacts
- Files touched: `src/retrieval/reranker.py`, `scripts/02_download_models.sh`, `tests/test_retrieval_components.py`
- Reports, plots, logs, or other evidence: this activity log
- Verification artifacts: passing retrieval unit tests and successful GPU `--verify` run without the old `score.weight` warning

## Result / Conclusions (Exact Answer to User)
> Warning означал, что мы грузили `Qwen3-Reranker-0.6B` неправильным классом модели: causal-LM checkpoint притворялся sequence-classification model, и Transformers создавал случайный `score.weight`. Это было неверное использование reranker. Теперь backend переведён на официальный Qwen path через `AutoModelForCausalLM` и yes/no scoring; warning исчез, offline/GPU verify проходят, и reranking теперь загружается корректно.
