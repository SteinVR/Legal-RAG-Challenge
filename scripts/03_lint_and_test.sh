#!/usr/bin/env bash
# 03_lint_and_test.sh — Run shell syntax checks, lint, compile check, and tests.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="$PROJECT_ROOT/.venv/bin/python"
cd "$PROJECT_ROOT"

export PYTHONPATH=.
export PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True

echo "=== Quality Gates ==="

echo "--- bash -n scripts/*.sh ---"
for script_path in scripts/*.sh; do
    bash -n "$script_path"
done
echo "shell syntax: PASS"

echo "--- ruff check ---"
"$PYTHON" -m ruff check src tests tools
echo "ruff: PASS"

echo "--- compileall ---"
"$PYTHON" -m compileall -q src tests tools
echo "compileall: PASS"

echo "--- pytest ---"
"$PYTHON" -m pytest tests/ -q --tb=short
echo "pytest: PASS"

echo "=== All Gates Passed ==="
