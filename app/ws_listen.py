import asyncio
import json
import websockets

async def listen():
    uri = "ws://127.0.0.1:8189/ws?clientId=diag_listener"
    print(f"Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as ws:
            print("Connected! Listening for messages...")
            for _ in range(10):
                msg = await asyncio.wait_for(ws.recv(), timeout=6.0)
                if isinstance(msg, str):
                    data = json.loads(msg)
                    msg_type = data.get("type")
                    msg_data = data.get("data", {})
                    print(f"[WS EVENT] Type: {msg_type} -> Data: {msg_data}")
                else:
                    print(f"[WS BINARY] {len(msg)} bytes")
    except asyncio.TimeoutError:
        print("Timeout waiting for more events (sampling might be calculating).")
    except Exception as e:
        print("WS error:", e)

asyncio.run(listen())
