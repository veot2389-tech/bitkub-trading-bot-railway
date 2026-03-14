#!/bin/bash
# 🦅 Turbo DGT v8.8 - The Final Immortal Upgrade
echo "🚀 [UPGRADE] เริ่มการอัปเกรดเป็น v8.8..."

# 1. ขอสิทธิ์ Root
sudo -v

# 2. ปิดระบบเดิม (กวาดล้าง)
echo "🧹 [CLEAN] กำลังปิดบอททุกตัวที่ค้างอยู่..."
sudo systemctl stop turbodgt 2>/dev/null
sudo systemctl disable turbodgt 2>/dev/null
powershell.exe -Command "Stop-Process -Name python,python3,pythonw -Force -ErrorAction SilentlyContinue" 2>/dev/null
sudo pkill -9 python 2>/dev/null
sudo pkill -9 python3 2>/dev/null
sudo fuser -k 5005/tcp 2>/dev/null

# 3. สร้างไฟล์ Service ใหม่
echo "🛠 [SERVICE] กำลังตั้งค่าระบบฆ่าไม่ตาย (Systemd)..."
PROJECT_DIR=$(pwd)
USER_NAME=$(whoami)

sudo bash -c "cat <<EOF > /etc/systemd/system/turbodgt.service
[Unit]
Description=Turbo DGT v8.8 Trading Bot
After=network.target

[Service]
ExecStart=$PROJECT_DIR/venv/bin/python3 $PROJECT_DIR/trading_bot_v8.py
WorkingDirectory=$PROJECT_DIR
StandardOutput=inherit
StandardError=inherit
Restart=always
RestartSec=10
User=$USER_NAME
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF"

# 4. เริ่มระบบใหม่
echo "✅ [START] เริ่มรันระบบ v8.8 เบื้องหลัง..."
sudo systemctl daemon-reload
sudo systemctl enable turbodgt
sudo systemctl start turbodgt

echo "✨ [SUCCESS] อัปเกรดเสร็จสิ้น! บอททำงานเองอัตโนมัติแล้วครับ"
echo "เช็คสถานะด้วยคำสั่ง: journalctl -u turbodgt -f"
