#!/usr/bin/env bash
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [ -x "$ROOT/venv/bin/python" ]; then
    PY="$ROOT/venv/bin/python"
elif [ -x "/opt/venv/bin/python" ]; then
    PY="/opt/venv/bin/python"
else
    PY="python3"
fi

exec "$PY" "$ROOT/launcher.py" --status
