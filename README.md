# LTX 2.5 Video Enhancement Studio 🎬✨

An enterprise-grade, turnkey Video-to-Video (V2V) Enhancement and Restoration Studio powered by **Lightricks LTX-2.5 22B Distilled DiT**, **Gemma 4 12B**, and **In-Context LoRAs (IC-LoRA)**, optimized specifically for **NVIDIA RTX 5090 (Blackwell)** and high-VRAM GPUs.

---

## 🌟 Key Features

* **High-Fidelity Enhancement**:
  * **Refine Details Mode**: Sharpens textures, boosts facial clarity, and adds photographic grain using `ltx-2.5-22b-ic-lora-refine-details-1.0`.
  * **Restore & Colorize Mode**: Removes compression artifacts, sepia tints, flicker, and scratches from old or low-quality footage using `ltx-2.5-22b-ic-lora-restore-1.0`.
* **Flexible Resolution Presets**: Native support for **FullHD (1080p)** and **4K** Tiled Fusion upscaling.
* **Lossless Audio Preservation**: Automatically extracts original audio, synchronizes with temporal latent windows ($8n+1$ frames alignment via FFmpeg), and remuxes losslessly into the final enhanced video.
* **Modern Web Interface**: Responsive, dark-mode web application featuring:
  * Drag-and-drop video upload with metadata analysis (`ffprobe`).
  * Live generation progress and streaming preview frames via WebSocket.
  * Real-time GPU & VRAM status monitoring.
  * Adaptive ETA calculation based on historical render speeds ($s/\text{video } s$).
  * Persistent job history with play, download, and cancel capabilities.
* **RTX 5090 Blackwell Optimization**:
  * Custom isolated ComfyUI worker environment configured with `PYTORCH_CUDA_ALLOC_CONF="backend:native"` to prevent segmentation faults and allocator issues on Blackwell architectures.
  * Zero memory interference with other services (built-in mutual exclusion and VRAM checks).

---

## 🏗️ Architecture Overview

```
ltx-enhancer/
├── app/
│   ├── server.py              # Aiohttp REST API & static web file server (Port 7860)
│   ├── pipeline.py            # Video analysis, frame alignment, audio muxing & workflow submission
│   ├── workflow_builder.py    # Builds dynamic ComfyUI API graphs (Tiled Fusion, IC-LoRA, VAE)
│   ├── gpu_manager.py         # FIFO queue, GPU mutual exclusion, VRAM monitor
│   ├── stats_manager.py       # Tracks historical render performance & adaptive ETAs
│   └── static/                # Modern Web UI (index.html, style.css, app.js)
├── comfy_backend/             # Isolated ComfyUI engine running on Port 8189
├── custom_nodes/
│   ├── websocket_image_save.py # Custom node streaming live preview frames via WebSocket
│   └── ComfyUI-LTXVideo/      # Official Lightricks LTXVideo custom node suite
├── models/
│   ├── extra_model_paths.yaml # ComfyUI configuration mapping models
│   ├── diffusion_models/      # ltx-2.5-22b-distilled-transformer (~21.5 GB)
│   ├── text_encoders/         # gemma4-12b-with-proj-ltx-2.5 (~15.4 GB)
│   ├── vae/                   # Audio VAE & Video VAE conv (~1.75 GB)
│   └── loras/                 # IC-LoRA Refine & Restore (~3.0 GB)
├── worker_supervisor.py       # Supervisor loop managing isolated worker with auto-recovery
├── start.sh                   # Launches both ComfyUI worker (8189) and Web Studio (7860)
├── start_worker.sh            # Launches worker supervisor in background
├── start_server.sh            # Launches web server in background
├── stop.sh                    # Gracefully terminates all LTX processes
├── setup.sh                   # One-click environment setup script
├── download_models.py         # Master downloader for all required weights
├── download_core_models.py    # Downloads DiT transformer and Gemma 4
├── download_vaes.py           # Downloads Audio & Video VAEs
├── download_loras.py          # Downloads IC-LoRA models
├── requirements.txt           # Python dependencies
└── README.md
```

---

## ⚡ Quickstart Guide

### 1. Requirements
* **Operating System**: Linux (Ubuntu 20.04+ recommended)
* **GPU**: NVIDIA GPU with 24GB+ VRAM (RTX 5090, RTX 4090, A100, H100)
* **CUDA**: 12.1+
* **System Packages**: `ffmpeg`, `ffprobe`, `git`, `python3` (3.10+ recommended)

### 2. Installation
Clone the repository and run the setup script:
```bash
git clone https://github.com/underworldhistory1-ctrl/ltx-2.5-enhancer.git
cd ltx-2.5-enhancer

# Make scripts executable
chmod +x *.sh

# Run turnkey setup
bash setup.sh
```

### 3. Download Models
Download all required model weights automatically (~41 GB total):
```bash
# Download all models (Core DiT, Gemma 4, VAEs, and IC-LoRAs)
python3 download_models.py --all

# Or download selectively:
python3 download_models.py --vae
python3 download_models.py --loras
python3 download_models.py --core
```

*Note*: If downloading gated Hugging Face weights directly, you can provide your token:
```bash
python3 download_models.py --loras --hf-token "YOUR_HF_TOKEN"
```

### 4. Launch the Studio
Start the isolated worker and web interface:
```bash
bash start.sh
```
* **Web Studio**: Open your browser at `http://<your-server-ip>:7860`
* **Internal ComfyUI Worker**: Runs on `http://127.0.0.1:8189`
* **Logs**: Check `logs/web_server.log` and `logs/comfy_worker.log`

To stop the services cleanly:
```bash
bash stop.sh
```

---

## 🔧 RTX 5090 Blackwell PyTorch Allocator Fix

On NVIDIA Blackwell GPUs (RTX 5090), the default PyTorch `cudaMalloc` memory allocator can occasionally cause segmentation faults during heavy DiT tensor allocations. This repository solves this at the supervisor level in `worker_supervisor.py`:
```python
worker_env["PYTORCH_CUDA_ALLOC_CONF"] = "backend:native"
worker_env["PYTORCH_ALLOC_CONF"] = "backend:native"
```
Combined with ComfyUI launch flags `--disable-cuda-malloc`, `--cache-none`, and `--fp16-intermediates`, this ensures maximum stability and zero crashes during sustained 4K video rendering.

---

## 📡 REST API Reference

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/api/upload` | `POST` | Upload a video file (`multipart/form-data`) |
| `/api/jobs` | `POST` | Submit a new enhancement job (`JSON`) |
| `/api/jobs` | `GET` | List all queued and completed jobs |
| `/api/jobs/{id}` | `GET` | Get status and details of a specific job |
| `/api/jobs/{id}/cancel` | `POST` | Cancel a running or queued job |
| `/api/jobs/{id}` | `DELETE`| Remove a job and its records |
| `/api/gpu_status` | `GET` | Real-time GPU utilization, VRAM usage & availability |
| `/api/stats` | `GET` | Historical render metrics and average rates |

---

## 📄 License
This project is released under the MIT License. Underlying weights and models are subject to their respective licenses from Lightricks and Google.
