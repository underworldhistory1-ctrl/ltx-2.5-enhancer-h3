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

"$PY" "$ROOT/launcher.py" --stop 2>/dev/null || true

# Force kill lingering ports if still occupied
fuser -k 7860/tcp 2>/dev/null || true
fuser -k 8189/tcp 2>/dev/null || true
