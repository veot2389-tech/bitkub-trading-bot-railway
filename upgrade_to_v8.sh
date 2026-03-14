#!/bin/bash
# 🦅 Turbo DGT v8.8 - Immortal System Upgrade
echo -e "\e[1;34m🚀 [UPGRADE] กำลังเปลี่ยนระบบเดิมให้กลายเป็นเครื่องจักรผลิตเงิน v8.8...\e[0m"

# 1. ขอสิทธิ์ Root
sudo -v

# 2. ปิดและล้างระบบเก่าให้เกลี้ยง (ครั้งสุดท้าย)
echo -e "\e[1;31m🧹 [CLEAN] ล้างระบบเก่าและบอทผีทั้งหมด...\e[0m"
sudo systemctl stop turbodgt 2>/dev/null
powershell.exe -Command "Stop-Process -Name python,python3,pythonw -Force -ErrorAction SilentlyContinue" 2>/dev/null
sudo pkill -9 python 2>/dev/null

# 3. สร้างไฟล์ Service ใหม่ (จุดเด่นของระบบเดิมที่คุณชอบ)
echo -e "\e[1;33m🛠 [SERVICE] กำลังสร้างเกราะคุ้มกัน (Auto-Restart) ให้บอท v8.8...\e[0m"
PROJECT_DIR=$(pwd)
USER_NAME=$(whoami)

cat <<EOF | sudo tee /etc/systemd/system/turbodgt.service
[Unit]
Description=Turbo DGT v8.8 Trading Bot (The Immortal)
After=network.target

[Service]
ExecStart=$PROJECT_DIR/venv/bin/python3 $PROJECT_DIR/trading_bot_v8.py
WorkingDirectory=$PROJECT_DIR
StandardOutput=inherit
StandardError=inherit
Restart=always
RestartSec=5
User=$USER_NAME
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

# 4. เปิดใช้งานระบบใหม่
echo -e "\e[1;32m✅ [ENABLE] เปิดใช้งานระบบ Background Service แบบสมบูรณ์...\e[0m"
sudo systemctl daemon-reload
sudo systemctl enable turbodgt
sudo systemctl start turbodgt

echo -e "\e[1;36m✨ [SUCCESS] อัปเกรดเรียบร้อย! บอท v8.8 กำลังทำงานอยู่เบื้องหลังแล้วครับ\e[0m"
echo "คุณสามารถดูการทำงานได้ด้วยคำสั่ง: journalctl -u turbodgt -f"
