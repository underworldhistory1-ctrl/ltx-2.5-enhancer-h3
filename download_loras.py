import os
import sys
import time
import argparse
import urllib.request

DEFAULT_BASE = os.path.abspath(os.path.dirname(__file__))
BASE_DIR = os.environ.get("LTX_BASE_DIR", DEFAULT_BASE)
LORAS_DIR = os.path.join(BASE_DIR, "models", "loras")

LORAS = [
    {
        "name": "ltx-2.5-22b-ic-lora-refine-details-1.0.safetensors",
        "repo_id": "Lightricks/LTX-2.5-22b-IC-LoRA-Refine-Details",
        "filename": "ltx-2.5-22b-ic-lora-refine-details-1.0.safetensors",
        "expected_size": 1308787534, # ~1.31 GB
        "direct_url": "https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Refine-Details/resolve/main/ltx-2.5-22b-ic-lora-refine-details-1.0.safetensors"
    },
    {
        "name": "ltx-2.5-22b-ic-lora-restore-1.0.safetensors",
        "repo_id": "Lightricks/LTX-2.5-22b-IC-LoRA-Restore",
        "filename": "ltx-2.5-22b-ic-lora-restore-1.0.safetensors",
        "expected_size": 1711643914, # ~1.71 GB
        "direct_url": "https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Restore/resolve/main/ltx-2.5-22b-ic-lora-restore-1.0.safetensors"
    }
]

def download_lora(item, hf_token=None):
    name = item["name"]
    dest = os.path.join(LORAS_DIR, name)
    os.makedirs(LORAS_DIR, exist_ok=True)

    if os.path.exists(dest) and os.path.getsize(dest) == item["expected_size"]:
        print(f"[SKIP] {name} already exists ({round(os.path.getsize(dest)/1e9, 2)} GB).")
        return

    # Try huggingface_hub first if installed
    token = hf_token or os.environ.get("HF_TOKEN")
    try:
        from huggingface_hub import hf_hub_download
        print(f"[START] Downloading {name} via huggingface_hub...")
        downloaded_path = hf_hub_download(
            repo_id=item["repo_id"],
            filename=item["filename"],
            token=token,
            local_dir=LORAS_DIR
        )
        if os.path.getsize(downloaded_path) != item["expected_size"]:
            raise RuntimeError(f"Incomplete {name} download")
        print(f"[COMPLETE] {name} saved successfully via huggingface_hub!")
        return
    except Exception as e:
        print(f"[INFO] huggingface_hub download not used or failed ({e}). Falling back to direct HTTP...")

    # Fallback to direct download
    url = item["direct_url"]
    tmp_path = dest + ".tmp"
    headers = {"User-Agent": "Mozilla/5.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    existing_bytes = 0
    if os.path.exists(tmp_path):
        existing_bytes = os.path.getsize(tmp_path)
        headers["Range"] = f"bytes={existing_bytes}-"
        print(f"[RESUME] Found partial download of {name}: {existing_bytes / 1e9:.2f} GB.")

    req = urllib.request.Request(url, headers=headers)
    max_retries = 5
    for attempt in range(1, max_retries + 1):
        try:
            print(f"[START] Downloading {name} (attempt {attempt}/{max_retries})...")
            with urllib.request.urlopen(req, timeout=30) as resp:
                mode = "ab" if existing_bytes > 0 and resp.status == 206 else "wb"
                if mode == "wb":
                    existing_bytes = 0
                total_size = item["expected_size"]

                downloaded = existing_bytes
                last_log_time = time.time()
                last_downloaded = downloaded
                chunk_size = 4 * 1024 * 1024

                with open(tmp_path, mode) as f:
                    while True:
                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)

                        now = time.time()
                        if now - last_log_time >= 10:
                            elapsed = now - last_log_time
                            speed_mb = ((downloaded - last_downloaded) / elapsed) / (1024 * 1024)
                            pct = (downloaded / total_size * 100) if total_size else 0
                            print(f"  {name}: {downloaded / 1e9:.2f} GB / {total_size / 1e9:.2f} GB ({pct:.1f}%) @ {speed_mb:.1f} MB/s", flush=True)
                            last_log_time = now
                            last_downloaded = downloaded

            if os.path.getsize(tmp_path) != item["expected_size"]:
                raise RuntimeError(f"Incomplete {name} download")
            os.replace(tmp_path, dest)
            print(f"[COMPLETE] {name} successfully saved ({os.path.getsize(dest) / 1e9:.2f} GB)!\n")
            return
        except Exception as e:
            print(f"[WARN] Error during download of {name}: {e}. Retrying in 5 seconds...")
            time.sleep(5)
            if os.path.exists(tmp_path):
                existing_bytes = os.path.getsize(tmp_path)
                headers["Range"] = f"bytes={existing_bytes}-"
                req = urllib.request.Request(url, headers=headers)

    raise RuntimeError(f"Failed to download {name} after {max_retries} attempts.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download LTX-2.5 IC-LoRAs")
    parser.add_argument("--token", type=str, default=None, help="Hugging Face Token (optional)")
    args = parser.parse_args()

    for item in LORAS:
        download_lora(item, hf_token=args.token)
    print("ALL LORAS DOWNLOADED SUCCESSFULLY!")
