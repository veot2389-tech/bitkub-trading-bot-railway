import asyncio
import json
from bitkub_async import BitkubAsyncDriver

async def main():
    with open("config.json") as f:
        cfg = json.load(f)
    
    driver = BitkubAsyncDriver(cfg["api_key"], cfg["api_secret"])
    res = await driver.send_request("POST", "/api/v3/market/balances")
    print(json.dumps(res, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
