#!/bin/bash
set -e

DIR="${LTX_BASE_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
cd "$DIR"

echo "=========================================================="
echo " Setting up LTX 2.5 Video Enhancement Studio Environment"
echo " Directory: $DIR"
echo "=========================================================="

# 1. Create required directories
echo "[1/6] Creating directory structure..."
mkdir -p "$DIR/logs" "$DIR/temp" "$DIR/inputs" "$DIR/outputs"
mkdir -p "$DIR/models/diffusion_models"
mkdir -p "$DIR/models/text_encoders"
mkdir -p "$DIR/models/vae"
mkdir -p "$DIR/models/loras"

# 2. Check for ComfyUI backend
echo "[2/6] Checking ComfyUI backend..."
if [ ! -d "$DIR/comfy_backend" ]; then
    echo "Cloning official ComfyUI into $DIR/comfy_backend..."
    git clone https://github.com/comfyanonymous/ComfyUI.git "$DIR/comfy_backend"
    git -C "$DIR/comfy_backend" checkout --detach b65d1ffaca35fcda5889e120dcd0c8520553c7b2
else
    echo "ComfyUI backend already exists in $DIR/comfy_backend."
fi

# 3. Setup custom nodes
echo "[3/6] Setting up custom nodes..."
mkdir -p "$DIR/comfy_backend/custom_nodes"

# Copy websocket_image_save node
if [ -f "$DIR/custom_nodes/websocket_image_save.py" ]; then
    cp "$DIR/custom_nodes/websocket_image_save.py" "$DIR/comfy_backend/custom_nodes/"
    echo "Installed SaveImageWebsocket node."
fi

# Setup ComfyUI-LTXVideo
if [ ! -d "$DIR/comfy_backend/custom_nodes/ComfyUI-LTXVideo" ]; then
    if [ -d "$DIR/custom_nodes/ComfyUI-LTXVideo" ]; then
        echo "Linking local ComfyUI-LTXVideo to ComfyUI backend..."
        cp -r "$DIR/custom_nodes/ComfyUI-LTXVideo" "$DIR/comfy_backend/custom_nodes/"
    else
        echo "Cloning ComfyUI-LTXVideo repository..."
        git clone https://github.com/Lightricks/ComfyUI-LTXVideo.git "$DIR/comfy_backend/custom_nodes/ComfyUI-LTXVideo"
    fi
else
    echo "ComfyUI-LTXVideo is already installed in comfy_backend."
fi

# 4. Detect Python binary
echo "[4/6] Detecting Python environment..."
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

if [ -z "$PYTHON_BIN" ]; then
    echo "ERROR: No suitable Python executable found."
    exit 1
fi
echo "Using Python: $PYTHON_BIN"

if [ -f "$DIR/requirements.txt" ]; then
    echo "Verifying dependencies..."
    "$PYTHON_BIN" -m pip install -r "$DIR/requirements.txt" --quiet || true
fi

# 5. Check FFmpeg
echo "[5/6] Checking FFmpeg and FFprobe..."
if command -v ffmpeg >/dev/null 2>&1 && command -v ffprobe >/dev/null 2>&1; then
    echo "FFmpeg is available."
else
    echo "WARNING: ffmpeg not found in PATH."
fi

# 6. Model paths config
echo "[6/6] Verifying extra_model_paths.yaml..."
cat > "$DIR/models/extra_model_paths.yaml" <<EOF
ltx_models:
    base_path: $DIR/models
    diffusion_models: diffusion_models
    text_encoders: text_encoders
    vae: vae
    loras: loras
EOF

echo ""
echo "=========================================================="
echo " Setup complete! All paths and dependencies configured."
echo "=========================================================="
