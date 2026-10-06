#!/bin/bash

echo "Stopping LTX 2.5 Enhancer processes..."

# Stop worker supervisor python script
pkill -f "worker_supervisor.py" 2>/dev/null || true

# Stop port 8189 (LTX ComfyUI worker)
fuser -k 8189/tcp 2>/dev/null || true

# Stop port 7860 (LTX Web Studio)
fuser -k 7860/tcp 2>/dev/null || true

echo "LTX Enhancer stopped cleanly. Note: External processes (such as port 8188) were NOT affected."
