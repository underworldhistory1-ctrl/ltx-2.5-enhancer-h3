import json

with open('/root/ltx-enhancer/custom_nodes/ComfyUI-LTXVideo/example_workflows/2.5/LTX-2.5_V2V_TiledFusion_Upscale.json') as f:
    wf = json.load(f)

print("=== MAIN GRAPH NODES ===")
for n in wf.get("nodes", []):
    print(f"ID {n.get('id')}: {n.get('type')} | title: '{n.get('title')}'")
    for inp in n.get('inputs', []):
        print(f"    input: {inp.get('name')} (type: {inp.get('type')}, link: {inp.get('link')})")
    for out in n.get('outputs', []):
        print(f"    output: {out.get('name')} (type: {out.get('type')}, links: {out.get('links')})")

print("\n=== SUBGRAPHS IN DEFINITIONS ===")
for sg_id, sg in wf.get('definitions', {}).get('subgraphs', {}).items():
    print(f"\n--- Subgraph {sg_id}: {sg.get('name')} ---")
    for n in sg.get('nodes', []):
        print(f"  [{n.get('id')}] {n.get('type')} - '{n.get('title')}'")
        for inp in n.get('inputs', []):
            print(f"      in: {inp.get('name')} (link: {inp.get('link')})")
        for out in n.get('outputs', []):
            print(f"      out: {out.get('name')} (links: {out.get('links')})")
