#!/usr/bin/env python3
import os
import signal
import subprocess
import sys
import time

STOP = False

def handle_signal(sig, frame):
    global STOP
    STOP = True
    print("[SUPERVISOR] Caught termination signal, shutting down...", flush=True)

signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)

DEFAULT_BASE = "/root/ltx-enhancer" if os.path.exists("/root/ltx-enhancer") else os.path.abspath(os.path.dirname(__file__))
BASE_DIR = os.environ.get("LTX_BASE_DIR", DEFAULT_BASE)

# Python binary fallback
DEFAULT_PY = "/output/h3-stack/ComfyUI/ComfyUI/.venv/bin/python"
PYTHON_EXE = os.environ.get("PYTHON_EXE", DEFAULT_PY if os.path.exists(DEFAULT_PY) else sys.executable)
COMFY_DIR = os.path.join(BASE_DIR, "comfy_backend")
LOG_FILE = os.path.join(BASE_DIR, "logs", "comfy_worker.log")
EXTRA_PATHS = os.path.join(BASE_DIR, "models", "extra_model_paths.yaml")
OUTPUT_DIR = os.path.join(BASE_DIR, "comfy_backend", "output")
TEMP_DIR = os.path.join(BASE_DIR, "temp")

# Critical fix for RTX 5090 Blackwell PyTorch allocator
worker_env = os.environ.copy()
worker_env["PYTORCH_CUDA_ALLOC_CONF"] = "backend:native"
worker_env["PYTORCH_ALLOC_CONF"] = "backend:native"

CMD = [
    PYTHON_EXE,
    os.path.join(COMFY_DIR, "main.py"),
    "--listen", "127.0.0.1",
    "--port", "8189",
    "--extra-model-paths-config", EXTRA_PATHS,
    "--output-directory", OUTPUT_DIR,
    "--temp-directory", TEMP_DIR,
    "--disable-cuda-malloc",
    "--cache-none",
    "--fp16-intermediates",
    "--disable-pinned-memory",
    "--disable-async-offload"
]

print(f"[SUPERVISOR] Starting ComfyUI supervisor loop on port 8189 (native CUDA allocator)...", flush=True)

while not STOP:
    with open(LOG_FILE, "a") as log_f:
        log_f.write(f"\n--- [SUPERVISOR] Starting ComfyUI worker at {time.ctime()} ---\n")
        log_f.flush()
        
        proc = subprocess.Popen(
            CMD,
            cwd=COMFY_DIR,
            stdout=log_f,
            stderr=subprocess.STDOUT,
            env=worker_env
        )
        print(f"[SUPERVISOR] ComfyUI worker spawned (PID: {proc.pid})", flush=True)

        while not STOP:
            ret = proc.poll()
            if ret is not None:
                print(f"[SUPERVISOR] ComfyUI worker exited with code {ret}. Restarting in 2s...", flush=True)
                break
            time.sleep(1)

        if STOP:
            print("[SUPERVISOR] Terminating worker...", flush=True)
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
            break

    if not STOP:
        time.sleep(2)

print("[SUPERVISOR] Supervisor stopped.", flush=True)
