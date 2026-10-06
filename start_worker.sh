#!/bin/bash
set -e

DIR="${LTX_BASE_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
mkdir -p "$DIR/logs" "$DIR/comfy_backend/output" "$DIR/temp"

# Auto-detect python binary
PYTHON_BIN=""
for candidate in \
    "$PYTHON_EXE" \
    "/output/h3-stack/ComfyUI/ComfyUI/.venv/bin/python" \
    "/output/h3-studio-v2/.venv/bin/python" \
    "$(which python3 2>/dev/null)" \
    "$(which python 2>/dev/null)"; do
    if [ -n "$candidate" ] && [ -x "$candidate" ]; then
        PYTHON_BIN="$candidate"
        break
    fi
done

echo "Checking if worker supervisor on port 8189 is already running..."
if curl -s http://127.0.0.1:8189/system_stats >/dev/null 2>&1; then
    echo "Worker on port 8189 is already up."
else
    echo "Launching worker supervisor on 127.0.0.1:8189 with $PYTHON_BIN..."
    cd "$DIR"
    nohup "$PYTHON_BIN" worker_supervisor.py \
        > "$DIR/logs/supervisor.log" 2>&1 &
    echo "ComfyUI worker supervisor started (PID: $!)."
fi
