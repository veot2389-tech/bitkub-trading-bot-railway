#!/bin/bash
# 🦅 Turbo DGT v9.0 "Grid All" - The Definitive Launcher
echo -e "\e[1;34m🚀 [SYSTEM] กำลังเริ่มมาตรการขั้นสูงสุดกวาดล้าง Conflict...\e[0m"

# 3. กวาดล้างฝั่ง Linux (WSL) - แบบล้างบาง
echo -e "\e[1;31m💀 [KILL LINUX] กวาดล้างระบบที่ค้างอยู่ใน WSL...\e[0m"
# ฆ่า Watchdog
pkill -9 -f watchdog.sh 2>/dev/null

# ฆ่า Python ทั้งหมด
pkill -9 python 2>/dev/null
pkill -9 python3 2>/dev/null
killall -9 python3 2>/dev/null

# เคลียร์พอร์ต
fuser -k 5000/tcp 5005/tcp 25005/tcp 25006/tcp 2>/dev/null

# 4. ล้าง Webhook และสัญญาณที่ค้างในเซิร์ฟเวอร์ Telegram
echo -e "\e[1;33m🌐 [NETWORK] ตัดสัญญาณค้างที่เซิร์ฟเวอร์ Telegram...\e[0m"
TOKEN=$(grep -oP '(?<="telegram_token": ")[^"]*' config.json)
curl -s "https://api.telegram.org/bot$TOKEN/deleteWebhook" > /dev/null

# 5. พักระบบและรอจนกว่าพอร์ตจะว่างจริง (Cooldown)
echo -e "\e[1;33m⏳ [WAIT] รอระบบเคลียร์สัญญาณและพอร์ตค้าง...\e[0m"
for i in {1..5}; do
    CHECK=$(ss -tunl | grep :25006)
    if [ -z "$CHECK" ]; then
        break
    fi
    echo "พอร์ต 25006 ยังไม่ว่าง... รออีกนิวนิด ($i/5)"
    sleep 2
done
sleep 1

# 6. ตั้งค่าตำแหน่งโฟลเดอร์ (รองรับช่องว่างในชื่อ)
PROJECT_DIR=$(pwd)
cd "$PROJECT_DIR"
if [ -d "venv" ]; then source venv/bin/activate 2>/dev/null; fi

# 7. เริ่มรัน (ใช้พอร์ตใหม่ 5005)
echo -e "\e[1;32m🚀 [LAUNCH] เริ่มรัน Turbo DGT v9.0 'Grid All' บนพอร์ตใหม่ 5005...\e[0m"
export PYTHONUNBUFFERED=1
python3 trading_bot_v8.py
