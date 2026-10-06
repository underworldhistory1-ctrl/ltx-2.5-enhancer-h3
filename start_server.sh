#!/bin/bash
set -e

DIR="${LTX_BASE_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
mkdir -p "$DIR/logs" "$DIR/inputs" "$DIR/outputs"

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

echo "Checking if web studio on port 7860 is already running..."
if curl -s http://127.0.0.1:7860/api/jobs >/dev/null 2>&1; then
    echo "Web studio on port 7860 is already running."
else
    echo "Launching Web Studio on port 7860 with $PYTHON_BIN..."
    cd "$DIR/app"
    nohup "$PYTHON_BIN" server.py \
        > "$DIR/logs/web_server.log" 2>&1 &
    echo "Web Studio started (PID: $!)."
fi
