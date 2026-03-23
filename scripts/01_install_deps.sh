#!/usr/bin/env bash
# 01_install_deps.sh — Install project dependencies into .venv.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="$PROJECT_ROOT/.venv/bin/python"
PADDLE_GPU_VERSION="3.3.0"

select_paddle_gpu_wheel_url() {
    local python_minor
    python_minor="$("$PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"

    case "$python_minor" in
        3.11)
            printf '%s\n' "https://paddle-whl.bj.bcebos.com/stable/cu126/paddlepaddle-gpu/paddlepaddle_gpu-${PADDLE_GPU_VERSION}-cp311-cp311-linux_x86_64.whl"
            ;;
        3.12)
            printf '%s\n' "https://paddle-whl.bj.bcebos.com/stable/cu126/paddlepaddle-gpu/paddlepaddle_gpu-${PADDLE_GPU_VERSION}-cp312-cp312-linux_x86_64.whl"
            ;;
        *)
            echo "FAIL: pinned paddlepaddle-gpu wheel is only defined for Python 3.11 and 3.12"
            exit 1
            ;;
    esac
}

PADDLE_GPU_WHEEL_URL="$(select_paddle_gpu_wheel_url)"

# Prevent import-time hoster probes during offline or firewalled installs.
export PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True

echo "=== Installing Dependencies ==="

uv pip install --python "$PYTHON" -e ".[paddle,dev]"

# Install the Paddle GPU runtime as a direct wheel with no dependency resolution
# so the existing CUDA/NVIDIA stack and local wheel cache remain untouched.
uv pip install --python "$PYTHON" --no-deps "$PADDLE_GPU_WHEEL_URL"

echo "--- Validating key imports ---"
"$PYTHON" -c "
import sentence_transformers; print(f'sentence-transformers {sentence_transformers.__version__}')
import transformers; print(f'transformers {transformers.__version__}')
import huggingface_hub; print(f'huggingface_hub {huggingface_hub.__version__}')
import qdrant_client; print('qdrant-client OK')
import torch; print(f'torch {torch.__version__} (CUDA: {torch.cuda.is_available()})')
import fitz; print(f'pymupdf {fitz.__version__}')
import httpx; print(f'httpx {httpx.__version__}')
import pydantic; print(f'pydantic {pydantic.__version__}')
import paddle; print(f'paddle {paddle.__version__} (compiled with CUDA: {paddle.device.is_compiled_with_cuda()})')
import paddleocr; print(f'paddleocr {paddleocr.__version__}')
"
if [ -x "$PROJECT_ROOT/.venv/bin/hf" ]; then
    echo "hf CLI: OK"
else
    echo "FAIL: hf CLI missing from .venv/bin/hf"
    exit 1
fi

echo "=== Dependencies OK ==="
