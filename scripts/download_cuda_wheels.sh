#!/bin/bash
# Fast multi-connection download of NVIDIA CUDA wheels for torch cu124.
# Uses aria2c (16 connections per file) to bypass PyPI single-connection limits.
#
# Prerequisites: sudo pacman -S aria2
# Usage: bash scripts/download_cuda_wheels.sh
# Then:  uv sync --find-links /tmp/cuda-wheels

set -eo pipefail

WHEEL_DIR="/tmp/cuda-wheels"
CONNECTIONS=16
PYTHON_TAG="cp312"
PLATFORM_TAG="x86_64"

command -v aria2c >/dev/null 2>&1 || {
    echo "aria2c not found. Install: sudo pacman -S aria2"
    exit 1
}

mkdir -p "$WHEEL_DIR"

declare -A PACKAGES=(
    ["nvidia-cublas-cu12"]="12.4.5.8"
    ["nvidia-cudnn-cu12"]="9.1.0.70"
    ["nvidia-cufft-cu12"]="11.2.1.3"
    ["nvidia-cusolver-cu12"]="11.6.1.9"
    ["nvidia-cusparse-cu12"]="12.3.1.170"
    ["nvidia-cusparselt-cu12"]="0.6.2"
    ["nvidia-nccl-cu12"]="2.21.5"
    ["triton"]="3.2.0"
)

resolve_url() {
    local pkg="$1" ver="$2"
    curl -sL "https://pypi.org/pypi/$pkg/$ver/json" | python3 -c "
import json, sys, re
data = json.load(sys.stdin)
for f in data.get('urls', []):
    fn = f['filename']
    # Only accept x86_64 manylinux wheels; avoid accidental aarch64.
    if not fn.endswith('.whl'):
        continue
    if ('$PYTHON_TAG' not in fn) and ('py3' not in fn):
        continue
    if 'aarch64' in fn or 'arm64' in fn:
        continue
    if not re.search(r'(manylinux[^/]*x86_64|linux_x86_64)', fn):
        continue
    print(f['url'])
    break
"
}

total=${#PACKAGES[@]}
current=0

for pkg in "${!PACKAGES[@]}"; do
    ver="${PACKAGES[$pkg]}"
    current=$((current + 1))
    echo ""
    echo "[$current/$total] $pkg $ver"

    url=$(resolve_url "$pkg" "$ver")

    if [ -z "$url" ]; then
        echo "  SKIP: no compatible wheel found"
        continue
    fi

    filename=$(basename "${url%%#*}")

    if [ -f "$WHEEL_DIR/$filename" ]; then
        echo "  CACHED: $filename"
        continue
    fi

    echo "  URL: $url"
    aria2c -x "$CONNECTIONS" -s "$CONNECTIONS" \
        --file-allocation=none \
        --summary-interval=5 \
        -d "$WHEEL_DIR" -o "$filename" \
        "$url"
done

echo ""
echo "=== All wheels in $WHEEL_DIR ==="
ls -lh "$WHEEL_DIR"/*.whl 2>/dev/null
echo ""
echo "Next step:"
echo "  cd $(pwd) && uv sync --find-links $WHEEL_DIR"
