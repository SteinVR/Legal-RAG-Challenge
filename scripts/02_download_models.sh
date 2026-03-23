#!/usr/bin/env bash
# 02_download_models.sh — Download retrieval models with visible progress and verify local GPU readiness.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="$PROJECT_ROOT/.venv/bin/python"
HF_BIN="$PROJECT_ROOT/.venv/bin/hf"
EMBED_REPO="Qwen/Qwen3-Embedding-0.6B"
RERANK_REPO="Qwen/Qwen3-Reranker-0.6B"
MAX_WORKERS="${HF_DOWNLOAD_MAX_WORKERS:-8}"

usage() {
    cat <<'EOF'
Usage:
  ./scripts/02_download_models.sh
  ./scripts/02_download_models.sh --verify

Modes:
  default   Download the embedder and reranker into the active Hugging Face cache with visible progress.
  --verify  Validate that both models load from cache offline, then require a working CUDA runtime for GPU smoke tests.
EOF
}

ensure_tooling() {
    if [ ! -x "$PYTHON" ]; then
        echo "FAIL: Python interpreter not found at $PYTHON"
        exit 1
    fi
    if [ ! -x "$HF_BIN" ]; then
        echo "FAIL: Hugging Face CLI not found at $HF_BIN"
        exit 1
    fi
}

print_cache_context() {
    "$PYTHON" - <<'PY'
from huggingface_hub.constants import HF_HUB_CACHE
print(f"HF cache: {HF_HUB_CACHE}")
PY
}

download_models() {
    export PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True

    echo "=== Downloading Retrieval Models ==="
    print_cache_context
    echo "HF max workers: $MAX_WORKERS"

    echo "--- $EMBED_REPO ---"
    "$HF_BIN" download --max-workers "$MAX_WORKERS" "$EMBED_REPO"

    echo "--- $RERANK_REPO ---"
    "$HF_BIN" download --max-workers "$MAX_WORKERS" "$RERANK_REPO"

    echo "--- Cache summary ---"
    "$PYTHON" - <<'PY'
from huggingface_hub import scan_cache_dir

repos_of_interest = {
    "Qwen/Qwen3-Embedding-0.6B",
    "Qwen/Qwen3-Reranker-0.6B",
}
cache = scan_cache_dir()
for repo in cache.repos:
    if repo.repo_id in repos_of_interest:
        print(f"{repo.repo_id}: {repo.size_on_disk / 1e6:.1f} MB")
PY

    echo "=== Download Complete ==="
}

verify_models() {
    export HF_HUB_OFFLINE=1
    export PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True

    echo "=== Verifying Retrieval Models ==="
    print_cache_context

    "$PYTHON" - <<'PY'
import sys

import torch
from sentence_transformers import SentenceTransformer

from src.retrieval.reranker import TransformersQwenRerankerBackend

EMBED_REPO = "Qwen/Qwen3-Embedding-0.6B"
RERANK_QUERY = "what is the filing deadline?"
RERANK_DOCUMENT = "the filing deadline is 30 days after service."


def reranker_forward(device: str) -> float:
    backend = TransformersQwenRerankerBackend(device=device)
    score = backend.score(RERANK_QUERY, [RERANK_DOCUMENT])[0]
    return float(score)


print(f"torch: {torch.__version__}")
print(f"torch.cuda.is_available: {torch.cuda.is_available()}")
print(f"torch.version.cuda: {torch.version.cuda}")
print(f"torch.cuda.device_count: {torch.cuda.device_count()}")

embedder_cpu = SentenceTransformer(
    EMBED_REPO,
    trust_remote_code=True,
    local_files_only=True,
    device="cpu",
)
cpu_vectors = embedder_cpu.encode(
    ["smoke test"],
    convert_to_numpy=True,
    show_progress_bar=False,
    normalize_embeddings=True,
)
print(f"Embedder CPU smoke OK: shape={tuple(cpu_vectors.shape)}")

cpu_score = reranker_forward("cpu")
print(f"Reranker CPU smoke OK: score={cpu_score:.4f}")

if not torch.cuda.is_available():
    print("FAIL: model cache is valid, but CUDA is unavailable on this host.")
    sys.exit(2)

embedder_gpu = SentenceTransformer(
    EMBED_REPO,
    trust_remote_code=True,
    local_files_only=True,
    device="cuda",
)
gpu_vectors = embedder_gpu.encode(
    ["gpu smoke test"],
    convert_to_numpy=True,
    show_progress_bar=False,
    normalize_embeddings=True,
)
print(f"Embedder GPU smoke OK: shape={tuple(gpu_vectors.shape)}")

gpu_score = reranker_forward("cuda")
print(f"Reranker GPU smoke OK: score={gpu_score:.4f}")
print("=== Verification Complete ===")
PY
}

main() {
    ensure_tooling

    case "${1:-}" in
        "")
            download_models
            ;;
        --verify)
            verify_models
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo "FAIL: unknown argument '$1'"
            usage
            exit 1
            ;;
    esac
}

main "$@"
