#!/usr/bin/env bash
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

PIDFILE="$ROOT/state/studio.pid"
if [ -f "$PIDFILE" ]; then
    PID=$(cat "$PIDFILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "[INFO] Studio server is already running (PID $PID)."
        exit 0
    else
        rm -f "$PIDFILE"
    fi
fi

# Detect Python: prefer repository venv, then host virtualenvs, then python3
if [ -x "$ROOT/venv/bin/python" ]; then
    PY="$ROOT/venv/bin/python"
elif [ -x "/opt/venv/bin/python" ]; then
    PY="/opt/venv/bin/python"
elif [ -n "$CONDA_PREFIX" ] && [ -x "$CONDA_PREFIX/bin/python" ]; then
    PY="$CONDA_PREFIX/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PY="python3"
else
    PY="python"
fi

mkdir -p "$ROOT/logs" "$ROOT/state"
echo "[INFO] Starting LTX Video Enhancement Studio server on port 7860..."
nohup "$PY" studio/server.py < /dev/null > "$ROOT/logs/studio.log" 2>&1 &
SERVER_PID=$!
echo "$SERVER_PID" > "$PIDFILE"
sleep 2

if kill -0 "$SERVER_PID" 2>/dev/null; then
    echo "[SUCCESS] Studio server started with PID $SERVER_PID."
    echo "Web UI listening on port 7860"
else
    echo "[ERROR] Studio server failed to start. Last log lines:"
    tail -n 20 "$ROOT/logs/studio.log"
    exit 1
fi
