import requests
import json

def verify():
    url = "https://api.uptimerobot.com/v2/getMonitors"
    payload = "api_key=u3367616-1ef9a4aec3b8ae798ca9e8e9&format=json"
    headers = {
        'content-type': "application/x-www-form-urlencoded",
        'cache-control': "no-cache"
    }
    
    try:
        # Check UptimeRobot
        r = requests.post(url, data=payload, headers=headers)
        monitors = r.json()
        print("--- UptimeRobot Status ---")
        if monitors.get("stat") == "ok":
            for m in monitors.get("monitors", []):
                print(f"Name: {m['friendly_name']}")
                print(f"URL: {m['url']}")
                print(f"Status: {'🟢 Online' if m['status'] == 2 else '🔴 Offline'}")
                print(f"Interval: {m['interval']} seconds")
        else:
            print("Failed to get monitors from UptimeRobot")
            
        # Check Render Health directly
        print("\n--- Render Health Check ---")
        try:
            h = requests.get("https://bitkub-trading-bot-railway.onrender.com/health", timeout=10)
            print(f"Response: {h.text}")
            if h.status_code == 200:
                print("🟢 Render is responsive")
        except:
            print("🔴 Could not reach Render")
            
    except Exception as e:
        print(f"Error during verification: {e}")

verify()
