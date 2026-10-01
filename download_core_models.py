import os
import sys
import time
import urllib.request

BASE_DIR = os.environ.get("LTX_BASE_DIR", os.path.dirname(os.path.abspath(__file__)))

MODELS = [
    {
        "name": "gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors",
        "url": "https://www.modelscope.cn/api/v1/models/Lightricks/LTX-2.5/repo?Revision=master&FilePath=text_encoders%2Fgemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors",
        "dest": os.path.join(BASE_DIR, "models", "text_encoders", "gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors"),
        "expected_size": 15372969374 # verified model size
    },
    {
        "name": "ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors",
        "url": "https://www.modelscope.cn/api/v1/models/Lightricks/LTX-2.5/repo?Revision=master&FilePath=diffusion_models%2Fltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors",
        "dest": os.path.join(BASE_DIR, "models", "diffusion_models", "ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors"),
        "expected_size": 21504034224 # verified model size
    }
]

def download_file(item):
    name = item["name"]
    url = item["url"]
    dest = item["dest"]
    tmp_path = dest + ".tmp"
    
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    
    if os.path.exists(dest):
        actual_size = os.path.getsize(dest)
        if actual_size == item["expected_size"]:
            print(f"[SKIP] {name} already exists ({actual_size / 1e9:.2f} GB).", flush=True)
            return

    existing_bytes = 0
    if os.path.exists(tmp_path):
        existing_bytes = os.path.getsize(tmp_path)
        print(f"[RESUME] Found partial download of {name}: {existing_bytes / 1e9:.2f} GB.", flush=True)

    headers = {'User-Agent': 'Mozilla/5.0'}
    if existing_bytes > 0:
        headers['Range'] = f'bytes={existing_bytes}-'

    req = urllib.request.Request(url, headers=headers)
    
    max_retries = 10
    for attempt in range(1, max_retries + 1):
        try:
            print(f"[START] Downloading {name} (attempt {attempt}/{max_retries})...", flush=True)
            with urllib.request.urlopen(req, timeout=30) as resp:
                mode = 'ab' if existing_bytes > 0 and resp.status == 206 else 'wb'
                if mode == 'wb':
                    existing_bytes = 0
                
                total_size = None
                content_range = resp.headers.get('Content-Range')
                if content_range:
                    try:
                        total_size = int(content_range.split('/')[-1])
                    except Exception:
                        pass
                if not total_size and resp.headers.get('Content-Length'):
                    total_size = existing_bytes + int(resp.headers.get('Content-Length'))

                total_gb = total_size / 1e9 if total_size else 0
                print(f"[INFO] Mode: {mode}, Total expected size: {total_gb:.2f} GB", flush=True)

                downloaded = existing_bytes
                last_log_time = time.time()
                last_downloaded = downloaded
                chunk_size = 4 * 1024 * 1024 # 4MB buffer

                with open(tmp_path, mode) as f:
                    while True:
                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        now = time.time()
                        if now - last_log_time >= 10: # Log every 10 seconds
                            elapsed = now - last_log_time
                            speed_mb = ((downloaded - last_downloaded) / elapsed) / (1024 * 1024)
                            pct = (downloaded / total_size * 100) if total_size else 0
                            print(f"  {name}: {downloaded / 1e9:.2f} GB / {total_gb:.2f} GB ({pct:.1f}%) @ {speed_mb:.1f} MB/s", flush=True)
                            last_log_time = now
                            last_downloaded = downloaded

            if os.path.getsize(tmp_path) != item["expected_size"]:
                raise RuntimeError(f"Incomplete {name}: {os.path.getsize(tmp_path)} of {item['expected_size']} bytes")

            # Success
            os.rename(tmp_path, dest)
            print(f"[COMPLETE] {name} successfully saved ({os.path.getsize(dest) / 1e9:.2f} GB)!\n", flush=True)
            return

        except Exception as e:
            print(f"[WARN] Error during download of {name}: {e}. Retrying in 5 seconds...", flush=True)
            time.sleep(5)
            if os.path.exists(tmp_path):
                existing_bytes = os.path.getsize(tmp_path)
                headers['Range'] = f'bytes={existing_bytes}-'
                req = urllib.request.Request(url, headers=headers)

    raise RuntimeError(f"Failed to download {name} after {max_retries} attempts.")

if __name__ == "__main__":
    for item in MODELS:
        download_file(item)
    print("ALL CORE MODELS DOWNLOADED SUCCESSFULLY!", flush=True)
