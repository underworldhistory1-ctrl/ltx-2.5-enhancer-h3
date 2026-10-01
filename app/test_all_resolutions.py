from workflow_builder import build_v2v_workflow
import json
import urllib.request
import urllib.error

for test_res in ["Original", "HD", "FullHD", "4K"]:
    prompt = build_v2v_workflow(
        input_video_filename="946df2a9_h3_studio_0f39c15d3ebc_00001_.mp4",
        output_filename_prefix=f"test_{test_res.lower()}",
        mode="refine",
        resolution_preset=test_res,
        seed=42
    )

    data = json.dumps({"prompt": prompt}).encode('utf-8')
    req = urllib.request.Request("http://127.0.0.1:8189/prompt", data=data, headers={"Content-Type": "application/json"})

    try:
        with urllib.request.urlopen(req) as resp:
            res_obj = json.loads(resp.read().decode())
            print(f"[{test_res}] ACCEPTED -> prompt_id: {res_obj.get('prompt_id')}")
    except urllib.error.HTTPError as e:
        print(f"[{test_res}] HTTP ERROR {e.code}: {e.read().decode()[:300]}")
    except Exception as e:
        print(f"[{test_res}] ERROR: {e}")
