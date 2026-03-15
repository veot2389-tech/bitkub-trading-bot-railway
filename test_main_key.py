import requests

url = "https://api.uptimerobot.com/v2/getMonitors"
payload = "api_key=u3367616-1ef9a4aec3b8ae798ca9e8e9&format=json"
headers = {
    'content-type': "application/x-www-form-urlencoded",
    'cache-control': "no-cache"
}

try:
    response = requests.request("POST", url, data=payload, headers=headers)
    print(response.text)
except Exception as e:
    print(e)
