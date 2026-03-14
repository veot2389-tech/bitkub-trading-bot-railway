#!/bin/bash
# 🐕‍🦺 Turbo DGT Watchdog - ระบบคืนชีพบอทอัตโนมัติ
PROJECT_DIR="/mnt/c/Users/Asus/Desktop/Api sever"
cd "$PROJECT_DIR"

# เช็คว่ามี process ของบอทรันอยู่ไหม
if ! pgrep -f "trading_bot_v8.py" > /dev/null
then
    echo "[$(date)] ⚠️ บอทหยุดทำงาน! กำลังปลุกระบบขึ้นมาใหม่..." >> watchdog.log
    # รันผ่าน start.sh แบบปกติ (ไม่เล่นพื้นหลัง)
    bash start.sh
else
    echo "[$(date)] ✅ บอททำงานปกติ" > watchdog_status.txt
fi
