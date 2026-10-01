import os, urllib.request, time

BASE_DIR = os.environ.get("LTX_BASE_DIR", os.path.dirname(os.path.abspath(__file__)))

files = [
    {
        'url': 'https://www.modelscope.cn/api/v1/models/Lightricks/LTX-2.5/repo?Revision=master&FilePath=vae%2Fltx-2.5-audio-vae-bf16.safetensors',
        'dest': os.path.join(BASE_DIR, 'models', 'vae', 'ltx-2.5-audio-vae-bf16.safetensors'),
        'expected_size': 364866540
    },
    {
        'url': 'https://www.modelscope.cn/api/v1/models/Lightricks/LTX-2.5/repo?Revision=master&FilePath=vae%2Fltx-2.5-video-vae-conv-bf16.safetensors',
        'dest': os.path.join(BASE_DIR, 'models', 'vae', 'ltx-2.5-video-vae-conv-bf16.safetensors'),
        'expected_size': 1452269922
    }
]

for item in files:
    dest = item['dest']
    url = item['url']
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if os.path.exists(dest) and os.path.getsize(dest) == item['expected_size']:
        print(f"Already exists: {dest} ({round(os.path.getsize(dest)/1e9, 2)} GB)")
        continue
    print(f"Downloading {os.path.basename(dest)}...")
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as resp, open(dest + '.tmp', 'wb') as out_f:
        downloaded = 0
        last_t = time.time()
        while True:
            chunk = resp.read(1024 * 1024 * 4) # 4MB chunks
            if not chunk:
                break
            out_f.write(chunk)
            downloaded += len(chunk)
            if time.time() - last_t > 3:
                print(f"  {os.path.basename(dest)}: {round(downloaded/1e9, 2)} GB downloaded...")
                last_t = time.time()
    if os.path.getsize(dest + '.tmp') != item['expected_size']:
        raise RuntimeError(f"Incomplete {dest}: {os.path.getsize(dest + '.tmp')} of {item['expected_size']} bytes")
    os.replace(dest + '.tmp', dest)
    print(f"Successfully downloaded {os.path.basename(dest)}! Size: {round(os.path.getsize(dest)/1e9, 2)} GB")
