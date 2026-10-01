#!/usr/bin/env python3
"""
Master Model Downloader for LTX 2.5 Video Enhancement Studio.
Downloads:
1. Core Models: Gemma 4 12B Text Encoder (~15.4 GB) & LTX 2.5 22B Distilled Transformer (~21.5 GB)
2. VAEs: Audio VAE (~350 MB) & Video VAE (~1.4 GB)
3. IC-LoRAs: Refine Details (~1.3 GB) & Restore (~1.7 GB)
"""

import os
import sys
import argparse
import subprocess

def run_script(script_name, *extra_args):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(current_dir, script_name)
    if not os.path.exists(script_path):
        print(f"Error: Script {script_name} not found at {script_path}")
        return False
    cmd = [sys.executable, script_path] + list(extra_args)
    print(f"\n=======================================================")
    print(f"  Executing: {' '.join(cmd)}")
    print(f"=======================================================\n")
    ret = subprocess.call(cmd)
    return ret == 0

def main():
    parser = argparse.ArgumentParser(description="Download all or specific models for LTX 2.5 Video Enhancer")
    parser.add_argument("--all", action="store_true", help="Download all models (Core, VAEs, and LoRAs)")
    parser.add_argument("--core", action="store_true", help="Download Core Models (Gemma 4 + Distilled Transformer)")
    parser.add_argument("--vae", action="store_true", help="Download Audio and Video VAEs")
    parser.add_argument("--loras", action="store_true", help="Download IC-LoRAs (Refine & Restore)")
    parser.add_argument("--hf-token", type=str, default=None, help="Optional Hugging Face Token for gated LoRAs")

    args = parser.parse_args()

    # Default to --all if no specific flag was given
    if not (args.core or args.vae or args.loras):
        args.all = True

    success = True
    if args.all or args.vae:
        print("[1/3] Downloading VAEs...")
        if not run_script("download_vaes.py"):
            print("Warning: VAE download encountered issues.")
            success = False

    if args.all or args.loras:
        print("\n[2/3] Downloading IC-LoRAs...")
        lora_args = ["--token", args.hf_token] if args.hf_token else []
        if not run_script("download_loras.py", *lora_args):
            print("Warning: LoRA download encountered issues.")
            success = False

    if args.all or args.core:
        print("\n[3/3] Downloading Core Models (Gemma 4 & Distilled Transformer)...")
        if not run_script("download_core_models.py"):
            print("Warning: Core model download encountered issues.")
            success = False

    if success:
        print("\n=======================================================")
        print("  ALL REQUESTED MODELS DOWNLOADED AND VERIFIED!  ")
        print("=======================================================\n")
    else:
        print("\n[!] Some model downloads failed or need retry. Review messages above.")

if __name__ == "__main__":
    main()
