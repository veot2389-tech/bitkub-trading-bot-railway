import asyncio
import websockets
import json

async def test_ws():
    url = "wss://api.bitkub.com/websocket-api/1"
    symbols = ["thb_trx", "thb_btc"]
    async with websockets.connect(url) as ws:
        for sym in symbols:
            # Try both formats
            sub_msg = {"op": "sub", "id": f"t_{sym}", "topic": f"market.ticker.{sym.lower()}"}
            print(f"Sending: {sub_msg}")
            await ws.send(json.dumps(sub_msg))
            
        print("Waiting for messages...")
        for _ in range(10):
            msg = await ws.recv()
            print(f"Received: {msg}")

if __name__ == "__main__":
    asyncio.run(test_ws())
