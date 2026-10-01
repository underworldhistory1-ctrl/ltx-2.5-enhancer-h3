import urllib.request, json
import sys
sys.path.insert(0, '/root/ltx-enhancer/app')
from workflow_builder import build_v2v_workflow

prompt = build_v2v_workflow(
    input_video_path="/root/ltx-enhancer/inputs/4cc6f05d_h3_studio_0f39c15d3ebc_00001_.mp4",
    output_filename_prefix="test_dry_run",
    mode="refine",
    resolution_preset="FullHD"
)

# Test POST to /prompt
payload = json.dumps({"prompt": prompt}).encode('utf-8')
req = urllib.request.Request("http://127.0.0.1:8189/prompt", data=payload, headers={"Content-Type": "application/json"})

try:
    with urllib.request.urlopen(req) as resp:
        print("PROMPT VALIDATION SUCCESS:", resp.read().decode())
except urllib.error.HTTPError as e:
    print("HTTP Error:", e.code)
    print("Error Details:", e.read().decode())
