import requests

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
    print(response.text)
except Exception as e:
    print(f"Error: {e}")
