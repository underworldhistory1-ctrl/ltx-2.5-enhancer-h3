import json

path = '/root/ltx-enhancer/custom_nodes/ComfyUI-LTXVideo/example_workflows/2.5/LTX-2.5_V2V_TiledFusion_Upscale.json'
with open(path, 'r', encoding='utf-8') as f:
    wf = json.load(f)

subgraphs = wf.get('definitions', {}).get('subgraphs', {})
print(f"Total subgraphs: {len(subgraphs)}")
for sg_id, sg_data in subgraphs.items():
    print(f"\n--- Subgraph {sg_id} (Name: {sg_data.get('name')}) ---")
    for n in sg_data.get('nodes', []):
        print(f"  [{n.get('id')}] {n.get('type')} - {n.get('title')}: {str(n.get('widgets_values'))[:80]}")
