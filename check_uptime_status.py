import requests
import json

url = "https://api.uptimerobot.com/v2/getMonitors"
payload = {
    "api_key": "m802550420-538e9dd56a6dd4fba8510971",
    "format": "json"
}
headers = {
    "content-type": "application/x-www-form-urlencoded",
    "cache-control": "no-cache"
}

try:
    response = requests.post(url, data=payload, headers=headers)
    result = response.json()
    print(json.dumps(result, indent=2))
except Exception as e:
    print(f"Error: {e}")
