# LTX 2.5 Studio Models Directory

Model files are automatically downloaded by `launcher.py` or `installer/install.py`.
Weights can also be manually placed in their respective subdirectories:

- `models/diffusion_models/`
  - `ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors` (~21.5 GB)
- `models/text_encoders/`
  - `gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors` (~15.4 GB)
- `models/vae/`
  - `ltx-2.5-video-vae-bf16.safetensors` (~1.47 GB)
  - `ltx-2.5-audio-vae-bf16.safetensors` (~365 MB)
- `models/loras/`
  - `ltx-2.5-22b-ic-lora-refine-details-1.0.safetensors` (~1.31 GB)
  - `ltx-2.5-22b-ic-lora-pixel-spatial-upscaler-x2-1.0.safetensors` (~327 MB)
  - `ltx-2.5-22b-ic-lora-restore-1.0.safetensors` (~1.71 GB, optional)
- `models/unet/`
  - `LTX-2.5-Distilled-Q4_K_M.gguf` (~15.7 GB, optional low-VRAM path)

All models are mapped into ComfyUI via `config/extra_model_paths.yaml`.
