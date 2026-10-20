#!/usr/bin/env bash
# ==============================================================================
# LTX 2.5 Video Enhancement Studio — One-Click Automated Setup & Run
# ==============================================================================
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# Detect Python interpreter
if [ -x "$ROOT/venv/bin/python" ]; then
    PY="$ROOT/venv/bin/python"
elif [ -x "/opt/venv/bin/python" ]; then
    PY="/opt/venv/bin/python"
elif [ -n "$CONDA_PREFIX" ] && [ -x "$CONDA_PREFIX/bin/python" ]; then
    PY="$CONDA_PREFIX/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PY="python3"
elif command -v python >/dev/null 2>&1; then
    PY="python"
else
    echo "[ERROR] Python 3 is not installed or not in PATH."
    exit 1
fi

chmod +x *.sh 2>/dev/null || true

# Execute launcher with all forwarded arguments
exec "$PY" "$ROOT/launcher.py" "$@"
