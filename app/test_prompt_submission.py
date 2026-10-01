import json
import urllib.request
import urllib.error
from workflow_builder import build_v2v_workflow

prompt = build_v2v_workflow(
    input_video_filename="946df2a9_h3_studio_0f39c15d3ebc_00001_.mp4",
    output_filename_prefix="test_validation_run",
    mode="refine",
    resolution_preset="FullHD",
    seed=42
)

data = json.dumps({"prompt": prompt}).encode('utf-8')
req = urllib.request.Request("http://127.0.0.1:8189/prompt", data=data, headers={"Content-Type": "application/json"})

try:
    with urllib.request.urlopen(req) as resp:
        print("PROMPT ACCEPTED:", resp.read().decode())
except urllib.error.HTTPError as e:
    print("HTTP ERROR:", e.code, e.read().decode())
except Exception as e:
    print("ERROR:", e)
