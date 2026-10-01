import os
from typing import Dict, Any

def build_v2v_workflow(
    input_video_filename: str,
    output_filename_prefix: str,
    mode: str = "refine", # "refine" or "restore"
    resolution_preset: str = "FullHD", # "FullHD" or "4K"
    tile_size_preset: str = "HD",
    lora_strength: float = 1.0,
    positive_prompt: str = "high quality, ultra realistic, sharp focus, photographic detail, natural grain",
    negative_prompt: str = "worst quality, low quality, jpeg artifacts, blur, deformed, flicker",
    seed: int = 42,
    frame_count: int = 97
) -> Dict[str, Any]:
    """
    Constructs the verified ComfyUI API prompt dictionary for LTX-2.5 Video-to-Video
    Tiled Fusion enhancement with Refine Details or Restore IC-LoRA.
    """
    lora_filename = (
        "ltx-2.5-22b-ic-lora-refine-details-1.0.safetensors"
        if mode == "refine"
        else "ltx-2.5-22b-ic-lora-restore-1.0.safetensors"
    )

    # Map friendly resolution preset to LTXVGetTilingSizes allowed values: ['FullHD', '4K', '8K']
    res_lower = str(resolution_preset).lower()
    if "4k" in res_lower or "2160" in res_lower:
        mapped_output_size = "4K"
    elif "8k" in res_lower or "4320" in res_lower:
        mapped_output_size = "8K"
    else:
        mapped_output_size = "FullHD"

    # LTX temporal latents require 8n+1 frames; cover the entire source clip.
    latent_frames = ((max(1, int(frame_count)) - 1 + 7) // 8) * 8 + 1

    # Use filename relative to ComfyUI input folder
    video_basename = os.path.basename(input_video_filename)

    prompt = {
        # --- Model Loaders ---
        "audio_vae_loader": {
            "class_type": "VAELoader",
            "inputs": {
                "vae_name": "ltx-2.5-audio-vae-bf16.safetensors"
            }
        },
        "video_vae_loader": {
            "class_type": "VAELoader",
            "inputs": {
                "vae_name": "ltx-2.5-video-vae-conv-bf16.safetensors"
            }
        },
        "unet_loader": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": "ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors",
                "weight_dtype": "default"
            }
        },
        "clip_loader": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": "gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors",
                "type": "ltxv"
            }
        },
        "ic_lora_loader": {
            "class_type": "LTXICLoRALoaderModelOnly",
            "inputs": {
                "model": ["unet_loader", 0],
                "lora_name": lora_filename,
                "strength_model": float(lora_strength)
            }
        },

        # --- Video Source & Components ---
        "load_video": {
            "class_type": "LoadVideo",
            "inputs": {
                "file": video_basename
            }
        },
        "video_components": {
            "class_type": "GetVideoComponents",
            "inputs": {
                "video": ["load_video", 0]
            }
        },

        # --- Resolution & Tiling Setup ---
        "tiling_sizes": {
            "class_type": "LTXVGetTilingSizes",
            "inputs": {
                "image": ["video_components", 0],
                "width": 1920,
                "height": 1080,
                "frame_count": 97,
                "tile_size": tile_size_preset,
                "initial_canvas_size": "FullHD",
                "output_size": mapped_output_size
            }
        },
        "scale_guide": {
            "class_type": "ImageScale",
            "inputs": {
                "image": ["video_components", 0],
                "upscale_method": "lanczos",
                "width": ["tiling_sizes", 4], # output_width
                "height": ["tiling_sizes", 5], # output_height
                "crop": "disabled"
            }
        },
        "empty_latent": {
            "class_type": "EmptyLTXVLatentVideo",
            "inputs": {
                "width": ["tiling_sizes", 4],
                "height": ["tiling_sizes", 5],
                "length": latent_frames, # full clip; tile_frames only controls sampler windows
                "batch_size": 1
            }
        },

        # --- Conditioning ---
        "positive_encode": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "clip": ["clip_loader", 0],
                "text": positive_prompt
            }
        },
        "negative_encode": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "clip": ["clip_loader", 0],
                "text": negative_prompt
            }
        },
        "ltxv_cond": {
            "class_type": "LTXVConditioning",
            "inputs": {
                "positive": ["positive_encode", 0],
                "negative": ["negative_encode", 0],
                "frame_rate": ["video_components", 2] # fps (FLOAT)
            }
        },
        "encode_audio": {
            "class_type": "VAEEncodeAudio",
            "inputs": {
                "audio": ["video_components", 1],
                "vae": ["audio_vae_loader", 0]
            }
        },
        "set_audio_tokens": {
            "class_type": "LTXVSetAudioRefTokens",
            "inputs": {
                "positive": ["ltxv_cond", 0],
                "negative": ["ltxv_cond", 1],
                "audio_latent": ["encode_audio", 0]
            }
        },
        "ic_lora_guide": {
            "class_type": "LTXAddVideoICLoRAGuide",
            "inputs": {
                "positive": ["set_audio_tokens", 0],
                "negative": ["set_audio_tokens", 1],
                "vae": ["video_vae_loader", 0],
                "latent": ["empty_latent", 0],
                "image": ["scale_guide", 0],
                "frame_idx": 0,
                "strength": 1.0,
                "latent_downscale_factor": 1.0,
                "crop": "disabled",
                "use_tiled_encode": False,
                "use_streaming": True,
                "tile_frames": ["tiling_sizes", 7],
                "tile_size": 256,
                "tile_overlap": 64
            }
        },

        # --- Sampler (8-step Distilled Tiled Fusion) ---
        "sampler_select": {
            "class_type": "KSamplerSelect",
            "inputs": {
                "sampler_name": "euler"
            }
        },
        "manual_sigmas": {
            "class_type": "ManualSigmas",
            "inputs": {
                "sigmas": "1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0"
            }
        },
        "tiled_fusion_sampler": {
            "class_type": "LTXVTiledFusionSampler",
            "inputs": {
                "model": ["ic_lora_loader", 0],
                "positive": ["ic_lora_guide", 0],
                "negative": ["ic_lora_guide", 1],
                "latents": ["ic_lora_guide", 2],
                "sigmas": ["manual_sigmas", 0],
                "sampler": ["sampler_select", 0],
                "seed": int(seed),
                "cfg": 1.0,
                "tile_width": ["tiling_sizes", 2],
                "tile_height": ["tiling_sizes", 3],
                "overlap_frac": ["tiling_sizes", 6],
                "blend_var": 0.05,
                "grid_cycle": 1,
                "tile_frames": ["tiling_sizes", 7]
            }
        },

        # --- Decode & Video Creation ---
        "tiled_decode": {
            "class_type": "VAEDecodeTiled",
            "inputs": {
                "samples": ["tiled_fusion_sampler", 0],
                "vae": ["video_vae_loader", 0],
                "tile_size": 512,
                "overlap": 64,
                "temporal_size": 128,
                "temporal_overlap": 32
            }
        },
        "audio_decode": {
            "class_type": "LTXVAudioVAEDecode",
            "inputs": {
                "samples": ["encode_audio", 0],
                "audio_vae": ["audio_vae_loader", 0]
            }
        },
        "create_video": {
            "class_type": "CreateVideo",
            "inputs": {
                "images": ["tiled_decode", 0],
                "audio": ["audio_decode", 0],
                "fps": ["video_components", 2],
                "quality": 8,
                "color_space": "sRGB"
            }
        },
        "save_video": {
            "class_type": "SaveVideo",
            "inputs": {
                "video": ["create_video", 0],
                "filename_prefix": output_filename_prefix,
                "format": "auto",
                "codec": "auto"
            }
        }
    }

    return prompt
