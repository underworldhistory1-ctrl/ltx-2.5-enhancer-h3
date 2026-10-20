#!/usr/bin/env bash
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

echo "=========================================================="
echo "    LTX VIDEO ENHANCEMENT STUDIO - TURNKEY SETUP & RUN    "
echo "=========================================================="

# 1. Preflight checks
echo "[1/4] Checking storage & GPU environment..."
FREE_KB=$(df "$ROOT" 2>/dev/null | awk 'NR==2 {print $4}' || df /output | awk 'NR==2 {print $4}')
FREE_GB=$((FREE_KB / 1024 / 1024))
echo "Available disk space in $ROOT: ${FREE_GB} GB"
if [ "$FREE_GB" -lt 50 ]; then
    echo "[WARNING] Less than 50 GB free space. At least 120 GB recommended."
fi

if command -v nvidia-smi >/dev/null 2>&1; then
    GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader | head -1)
    echo "Detected GPU: $GPU_NAME"
else
    echo "[ERROR] No NVIDIA GPU detected. LTX Studio requires CUDA."
    exit 1
fi

# 2. Start Studio web server
echo "[2/4] Starting LTX Studio Web Server on port 7860..."
bash "$ROOT/start.sh"

# 3. Launch or verify installer
echo "[3/4] Triggering automatic installer in background..."
PY="/opt/venv/bin/python"
if [ -x "$ROOT/venv/bin/python" ]; then
    PY="$ROOT/venv/bin/python"
fi

if ! pgrep -f "install.py --root $ROOT" >/dev/null 2>&1; then
    nohup "$PY" "$ROOT/installer/install.py" --root "$ROOT" > "$ROOT/logs/installer.log" 2>&1 &
    echo "[INFO] Installer launched in background (PID $!)."
else
    echo "[INFO] Installer already running."
fi

# 4. Display instructions
echo "[4/4] Setup complete! Studio is active."
echo "=========================================================="
echo " Access URLs:"
echo "   Direct Web:      http://0.0.0.0:7860"
echo "   SSH Tunnel:      ssh -L 7860:127.0.0.1:7860 root@ssh.hyper.ai -p32393"
echo "                    Then open in local browser: http://localhost:7860"
echo " Monitoring & Logs:"
echo "   Live Status:     bash $ROOT/status.sh"
echo "   Server Log:      tail -f $ROOT/logs/studio.log"
echo "   Installer Log:   tail -f $ROOT/logs/installer.log"
echo " Operations:"
echo "   Stop:            bash $ROOT/stop.sh"
echo "   Restart:         bash $ROOT/restart.sh"
echo "=========================================================="
