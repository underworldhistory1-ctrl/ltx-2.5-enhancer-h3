import os
import sys
import time
import urllib.request

DEFAULT_BASE = os.path.abspath(os.path.dirname(__file__))
BASE_DIR = os.environ.get("LTX_BASE_DIR", DEFAULT_BASE)
VAE_DIR = os.path.join(BASE_DIR, "models", "vae")

FILES = [
    {
        "name": "ltx-2.5-audio-vae-bf16.safetensors",
        "url": "https://www.modelscope.cn/api/v1/models/Lightricks/LTX-2.5/repo?Revision=master&FilePath=vae%2Fltx-2.5-audio-vae-bf16.safetensors",
        "dest": os.path.join(VAE_DIR, "ltx-2.5-audio-vae-bf16.safetensors"),
        "expected_size": 364866540
    },
    {
        "name": "ltx-2.5-video-vae-conv-bf16.safetensors",
        "url": "https://www.modelscope.cn/api/v1/models/Lightricks/LTX-2.5/repo?Revision=master&FilePath=vae%2Fltx-2.5-video-vae-conv-bf16.safetensors",
        "dest": os.path.join(VAE_DIR, "ltx-2.5-video-vae-conv-bf16.safetensors"),
        "expected_size": 1452269922
    }
]

def download_file(item):
    name = item["name"]
    dest = item["dest"]
    url = item["url"]
    expected_size = item["expected_size"]
    tmp_path = dest + ".tmp"

    os.makedirs(VAE_DIR, exist_ok=True)

    if os.path.exists(dest) and os.path.getsize(dest) == expected_size:
        print(f"[SKIP] {name} already exists ({round(expected_size / 1e9, 2)} GB).")
        return True

    existing_bytes = 0
    if os.path.exists(tmp_path):
        existing_bytes = os.path.getsize(tmp_path)
        if existing_bytes == expected_size:
            os.replace(tmp_path, dest)
            print(f"[COMPLETE] {name} was already downloaded; promoted tmp.")
            return True
        print(f"[RESUME] Found partial download of {name}: {round(existing_bytes / 1e9, 2)} GB.")

    headers = {"User-Agent": "Mozilla/5.0"}
    if existing_bytes > 0:
        headers["Range"] = f"bytes={existing_bytes}-"

    req = urllib.request.Request(url, headers=headers)
    for attempt in range(1, 6):
        try:
            print(f"[START] Downloading {name} (attempt {attempt}/5)...")
            with urllib.request.urlopen(req, timeout=30) as resp:
                mode = "ab" if existing_bytes > 0 and resp.status == 206 else "wb"
                if mode == "wb":
                    existing_bytes = 0

                downloaded = existing_bytes
                last_log = time.time()
                last_dl = downloaded
                chunk_size = 4 * 1024 * 1024

                with open(tmp_path, mode) as f:
                    while True:
                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)

                        now = time.time()
                        if now - last_log >= 10:
                            elapsed = now - last_log
                            speed = ((downloaded - last_dl) / elapsed) / (1024 * 1024)
                            pct = round(downloaded / expected_size * 100, 1)
                            print(f"  {name}: {round(downloaded / 1e9, 2)} / {round(expected_size / 1e9, 2)} GB ({pct}%) @ {speed:.1f} MB/s", flush=True)
                            last_log = now
                            last_dl = downloaded

            if os.path.getsize(tmp_path) == expected_size:
                os.replace(tmp_path, dest)
                print(f"[COMPLETE] {name} saved successfully!\n")
                return True
            else:
                print(f"[WARN] Size mismatch: {os.path.getsize(tmp_path)} != {expected_size}. Retrying...")
        except Exception as e:
            print(f"[WARN] Download error for {name}: {e}. Retrying in 5s...")
            time.sleep(5)
            if os.path.exists(tmp_path):
                existing_bytes = os.path.getsize(tmp_path)
                headers["Range"] = f"bytes={existing_bytes}-"
                req = urllib.request.Request(url, headers=headers)

    raise RuntimeError(f"Failed to download {name} after 5 attempts.")

if __name__ == "__main__":
    for item in FILES:
        download_file(item)
    print("ALL VAEs READY AND VALIDATED!")
