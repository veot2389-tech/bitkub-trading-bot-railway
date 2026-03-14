import requests
r = requests.get("https://api.bitkub.com/api/market/ticker")
data = r.json()
print(f"Keys: {list(data.keys())[:10]}")
if "THB_BTC" in data:
    print(f"BTC Price: {data['THB_BTC']['last']}")
else:
    print("THB_BTC not found in Ticker")
