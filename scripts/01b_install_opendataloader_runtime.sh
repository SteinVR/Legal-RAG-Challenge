#!/usr/bin/env bash
# 01b_install_opendataloader_runtime.sh — Install system + Python runtime for vendored opendataloader-pdf.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="$PROJECT_ROOT/.venv/bin/python"
OPENDATALOADER_ROOT="$PROJECT_ROOT/external/opendataloader-pdf"
OPENDATALOADER_PYTHON_DIR="$OPENDATALOADER_ROOT/python/opendataloader-pdf"
OPENDATALOADER_JAVA_DIR="$OPENDATALOADER_ROOT/java"
HEADLESS_JAVA_TOOL_OPTION="-Djava.awt.headless=true"

WITH_HYBRID=1
SKIP_SYSTEM_PACKAGES=0

usage() {
    cat <<'EOF'
Usage: scripts/01b_install_opendataloader_runtime.sh [options]

Options:
  --with-hybrid           Explicitly keep hybrid extras enabled.
  --without-hybrid        Skip hybrid-server extras and install only the base wrapper.
  --skip-system-packages  Do not install JDK/Maven; only build/install vendored artifacts.
  -h, --help              Show this help.

This script is intended for manual operator execution. It:
1. Installs Java + Maven with the detected package manager.
2. Builds the vendored opendataloader-pdf CLI JAR.
3. Installs the vendored Python wrapper into the repo .venv.
4. Verifies java, maven, the bundled JAR, and Python importability.
EOF
}

while (($# > 0)); do
    case "$1" in
    --with-hybrid)
        WITH_HYBRID=1
        ;;
    --without-hybrid)
        WITH_HYBRID=0
        ;;
    --skip-system-packages)
        SKIP_SYSTEM_PACKAGES=1
        ;;
    -h|--help)
        usage
        exit 0
        ;;
    *)
        echo "Unknown argument: $1" >&2
        usage >&2
        exit 1
        ;;
    esac
    shift
done

require_file() {
    local path="$1"
    if [[ ! -e "$path" ]]; then
        echo "FAIL: required path is missing: $path" >&2
        exit 1
    fi
}

require_cmd() {
    local name="$1"
    if ! command -v "$name" >/dev/null 2>&1; then
        echo "FAIL: required command is missing: $name" >&2
        exit 1
    fi
}

run_as_root() {
    if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
        "$@"
        return
    fi
    if command -v sudo >/dev/null 2>&1; then
        sudo "$@"
        return
    fi
    echo "FAIL: root privileges are required for system package installation, but sudo is not available." >&2
    exit 1
}

detect_package_manager() {
    local candidates=(pacman apt-get dnf brew)
    local candidate
    for candidate in "${candidates[@]}"; do
        if command -v "$candidate" >/dev/null 2>&1; then
            printf '%s\n' "$candidate"
            return
        fi
    done
    return 1
}

install_system_packages() {
    local package_manager
    if [[ "$SKIP_SYSTEM_PACKAGES" -eq 1 ]]; then
        echo "=== Skipping system package installation by request ==="
        return
    fi

    if command -v java >/dev/null 2>&1 && command -v mvn >/dev/null 2>&1; then
        echo "=== java and mvn already present; skipping system package installation ==="
        return
    fi

    if ! package_manager="$(detect_package_manager)"; then
        echo "FAIL: unsupported package manager. Install Java 11+ and Maven manually, then rerun with --skip-system-packages." >&2
        exit 1
    fi

    echo "=== Installing system packages via $package_manager ==="
    case "$package_manager" in
        pacman)
            run_as_root pacman -Sy --noconfirm jdk-openjdk maven
            ;;
        apt-get)
            run_as_root apt-get update
            run_as_root apt-get install -y openjdk-21-jdk maven
            ;;
        dnf)
            run_as_root dnf install -y java-21-openjdk-devel maven
            ;;
        brew)
            brew install openjdk@21 maven
            cat <<'EOF'
NOTE: Homebrew may require you to add OpenJDK to PATH manually, for example:
  export PATH="$(brew --prefix openjdk@21)/bin:$PATH"
EOF
            ;;
    esac
}

build_vendored_jar() {
    echo "=== Building vendored opendataloader-pdf JAR ==="
    require_cmd mvn
    require_file "$OPENDATALOADER_JAVA_DIR/pom.xml"
    (
        cd "$OPENDATALOADER_JAVA_DIR"
        mvn -DskipTests package
    )
}

install_python_wrapper() {
    local target
    local cleanup_readme=0

    require_cmd uv
    require_file "$PYTHON"
    require_file "$OPENDATALOADER_PYTHON_DIR/pyproject.toml"
    require_file "$OPENDATALOADER_ROOT/README.md"

    echo "=== Installing vendored Python wrapper into .venv ==="

    if [[ ! -f "$OPENDATALOADER_PYTHON_DIR/README.md" ]]; then
        cp "$OPENDATALOADER_ROOT/README.md" "$OPENDATALOADER_PYTHON_DIR/README.md"
        cleanup_readme=1
    fi

    if [[ "$WITH_HYBRID" -eq 1 ]]; then
        target="$OPENDATALOADER_PYTHON_DIR[hybrid]"
    else
        target="$OPENDATALOADER_PYTHON_DIR"
    fi

    uv pip install --python "$PYTHON" -e "$target"

    if [[ "$cleanup_readme" -eq 1 ]]; then
        rm -f "$OPENDATALOADER_PYTHON_DIR/README.md"
    fi
}

verify_runtime() {
    local jar_path
    local smoke_dir

    echo "=== Verifying runtime ==="
    require_cmd java
    require_cmd mvn
    java -version
    mvn -version

    jar_path="$("$PYTHON" - <<'PY'
from importlib.resources import files
print(files("opendataloader_pdf").joinpath("jar/opendataloader-pdf-cli.jar"))
PY
)"

    if [[ ! -f "$jar_path" ]]; then
        echo "FAIL: bundled JAR not found at $jar_path" >&2
        exit 1
    fi

    "$PYTHON" - <<'PY'
import opendataloader_pdf
from importlib.resources import files

jar_path = files("opendataloader_pdf").joinpath("jar/opendataloader-pdf-cli.jar")
print(f"opendataloader_pdf import OK: {opendataloader_pdf.__file__}")
print(f"bundled jar OK: {jar_path}")
PY

    if [[ -x "$PROJECT_ROOT/.venv/bin/opendataloader-pdf" ]]; then
        "$PROJECT_ROOT/.venv/bin/opendataloader-pdf" --help >/dev/null
        echo "opendataloader-pdf CLI wrapper: OK"
    else
        echo "FAIL: .venv/bin/opendataloader-pdf is missing" >&2
        exit 1
    fi

    smoke_dir="$(mktemp -d)"
    "$PYTHON" - <<'PY' "$smoke_dir"
import sys
from pathlib import Path

import fitz

base = Path(sys.argv[1])
pdf_path = base / "smoke.pdf"
doc = fitz.open()
page = doc.new_page()
page.insert_text((72, 72), "DIFC LAW NO. 1\nArticle 1\nSmoke parse for opendataloader runtime.")
doc.save(pdf_path)
doc.close()
PY
    JAVA_TOOL_OPTIONS="${JAVA_TOOL_OPTIONS:-} ${HEADLESS_JAVA_TOOL_OPTION}" \
        "$PROJECT_ROOT/.venv/bin/opendataloader-pdf" \
        "$smoke_dir/smoke.pdf" \
        --output-dir "$smoke_dir/out" \
        --format json \
        --table-method cluster \
        --reading-order xycut \
        --quiet
    if [[ ! -f "$smoke_dir/out/smoke.json" ]]; then
        echo "FAIL: opendataloader smoke parse did not produce JSON output" >&2
        exit 1
    fi
    echo "opendataloader smoke parse: OK"
}

main() {
    require_file "$PROJECT_ROOT/.venv"
    require_file "$OPENDATALOADER_ROOT"

    install_system_packages
    build_vendored_jar
    install_python_wrapper
    verify_runtime

    echo "=== opendataloader runtime is ready ==="
}

main "$@"
