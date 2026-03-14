import os
import subprocess
import json
import time
import requests

def run_cmd(cmd):
    try:
        return subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL).decode().strip()
    except:
        return ""

print("🚀 [FIX-409] เริ่มมาตรการกวาดล้างขั้นสูงสุด...")

# 1. ล้างฝั่ง Linux (WSL)
print("💀 กำลังล้างฝั่ง Linux...")
os.system("sudo systemctl stop turbodgt 2>/dev/null")
os.system("sudo fuser -k 5000/tcp 2>/dev/null")
os.system("sudo pkill -9 python 2>/dev/null")
os.system("sudo pkill -9 python3 2>/dev/null")

# 2. ล้างฝั่ง Windows (ผ่าน PowerShell)
print("💀 กำลังล้างฝั่ง Windows...")
# ฆ่าตามชื่อ Process
powershell_kills = [
    "Stop-Process -Name python -Force",
    "Stop-Process -Name python3 -Force",
    "Stop-Process -Name pythonw -Force",
    "Stop-Process -Name py -Force"
]
for p_cmd in powershell_kills:
    os.system(f'powershell.exe -Command "{p_cmd}" 2>/dev/null')

# ฆ่าตาม Port 5000 ใน Windows
kill_port_5000 = 'Get-NetTCPConnection -LocalPort 5000 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }'
os.system(f'powershell.exe -Command "{kill_port_5000}" 2>/dev/null')

# 3. ล้างสัญญาณ Telegram Server
print("🌐 กำลังล้างสัญญาณที่ Telegram Server...")
try:
    with open("config.json") as f:
        cfg = json.load(f)
        token = cfg.get("telegram_token")
        if token:
            requests.get(f"https://api.telegram.org/bot{token}/deleteWebhook")
            requests.get(f"https://api.telegram.org/bot{token}/getUpdates?offset=-1")
            print("✅ ล้างสัญญาณ Telegram สำเร็จ")
except Exception as e:
    print(f"❌ ล้างสัญญาณ Telegram พลาด: {e}")

print("⏳ รอระบบคลายตัว 10 วินาที (โปรดใจเย็นๆ)...")
time.sleep(10)
print("✨ ระบบสะอาดแล้ว! คุณสามารถรัน bash start.sh ได้ทันทีครับ")
