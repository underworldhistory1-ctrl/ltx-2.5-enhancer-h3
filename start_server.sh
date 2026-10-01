#!/bin/bash
set -e

DIR="${LTX_BASE_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
mkdir -p "$DIR/logs"

# Determine python binary
PYTHON_BIN="${PYTHON_EXE:-/output/h3-stack/ComfyUI/ComfyUI/.venv/bin/python}"
if [ ! -f "$PYTHON_BIN" ]; then
    PYTHON_BIN="$(command -v python3 || command -v python)"
fi

echo "Checking if web studio on port 7860 is already running..."
if curl -s http://127.0.0.1:7860/api/gpu_status >/dev/null 2>&1; then
    echo "Web studio on port 7860 is already running."
else
    echo "Launching LTX Web Studio on 0.0.0.0:7860 with $PYTHON_BIN..."
    cd "$DIR/app"
    nohup "$PYTHON_BIN" server.py \
        > "$DIR/logs/web_server.log" 2>&1 &
    echo "Web studio started (PID: $!)."
fi
