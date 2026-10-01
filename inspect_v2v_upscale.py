import json

path = '/root/ltx-enhancer/custom_nodes/ComfyUI-LTXVideo/example_workflows/2.5/LTX-2.5_V2V_TiledFusion_Upscale.json'
with open(path, 'r', encoding='utf-8') as f:
    wf = json.load(f)

for sg in wf['definitions']['subgraphs']:
    sg_id = sg.get('id')
    name = sg.get('name')
    nodes = sg.get('nodes', [])
    print(f"\n==================== Subgraph ID: {sg_id} | Name: '{name}' (nodes: {len(nodes)}) ====================")
    for n in nodes:
        print(f"  [{n.get('id')}] {n.get('type')} ('{n.get('title')}') widgets: {n.get('widgets_values')}")
