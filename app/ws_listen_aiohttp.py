import asyncio
import aiohttp
import json

async def listen():
    uri = "http://127.0.0.1:8189/ws?clientId=diag_listener"
    print(f"Connecting to {uri}...")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.ws_connect(uri) as ws:
                print("Connected! Listening for messages...")
                for _ in range(15):
                    try:
                        msg = await asyncio.wait_for(ws.receive(), timeout=4.0)
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            data = json.loads(msg.data)
                            msg_type = data.get("type")
                            msg_data = data.get("data", {})
                            print(f"[WS EVENT] Type: {msg_type} -> Data: {msg_data}")
                        elif msg.type == aiohttp.WSMsgType.BINARY:
                            print(f"[WS BINARY] {len(msg.data)} bytes")
                        elif msg.type == aiohttp.WSMsgType.CLOSED:
                            print("WS Closed")
                            break
                    except asyncio.TimeoutError:
                        print("Timeout waiting for next event...")
                        break
    except Exception as e:
        print("WS error:", e)

asyncio.run(listen())
