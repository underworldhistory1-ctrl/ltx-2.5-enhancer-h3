import urllib.request, json

nodes_to_inspect = ['GetVideoComponents', 'LTXVConditioning', 'LTXVSetAudioRefTokens', 'LoadVideo', 'VAEEncodeAudio']

for n in nodes_to_inspect:
    url = f'http://127.0.0.1:8189/object_info/{n}'
    try:
        data = json.loads(urllib.request.urlopen(url).read().decode())
        print(f"\n==================== {n} ====================")
        print("Inputs required:", list(data.get(n, {}).get('input', {}).get('required', {}).keys()))
        print("Inputs optional:", list(data.get(n, {}).get('input', {}).get('optional', {}).keys()))
        print("Outputs:", data.get(n, {}).get('output'))
        print("Output names:", data.get(n, {}).get('output_name'))
    except Exception as e:
        print(f"Error for {n}:", e)
