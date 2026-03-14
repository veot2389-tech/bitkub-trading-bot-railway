#!/bin/bash

# =================================================================
# 🚀 Turbo DGT v8.8 - Ultra Stable Systemd Setup (Fixed Path)
# =================================================================

# Get current directory and escape spaces for bash
PROJECT_DIR=$(pwd)
SERVICE_NAME="turbodgt"
USER_NAME=$USER

echo "🛡️ [1/4] ตรวจสอบความพร้อมของระบบ (Path: $PROJECT_DIR)..."

# 1. จัดการ Python Virtual Environment
if [ ! -d "venv" ]; then
    echo "📦 ไม่พบ venv, กำลังสร้างใหม่..."
    python3 -m venv venv
fi
PYTHON_EXE="$PROJECT_DIR/venv/bin/python3"

# 2. ติดตั้ง Dependencies ที่จำเป็น (ใช้เครื่องหมายอัญประกาศครอบตัวแปรที่มีช่องว่าง)
echo "📦 [2/4] อัปเดต Library (numpy, telebot, websockets, flask)..."
"$PYTHON_EXE" -m pip install --upgrade pip --quiet
"$PYTHON_EXE" -m pip install numpy pyTelegramBotAPI websockets flask aiohttp requests --quiet

# 3. สร้างไฟล์ Systemd Service (แบบรองรับช่องว่างใน Path)
echo "⚙️ [3/4] กำลังติดตั้ง Systemd Service..."
sudo bash -c "cat <<EOF > /etc/systemd/system/$SERVICE_NAME.service
[Unit]
Description=Turbo DGT v8.8 Mathematical Trading Bot
After=network.target

[Service]
Type=simple
User=$USER_NAME
WorkingDirectory=$PROJECT_DIR
ExecStart=\"$PYTHON_EXE\" trading_bot_v8.py
Restart=always
RestartSec=5
LimitNOFILE=65536
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF"

# 4. ตั้งค่า Logrotate
echo "📝 [4/4] ตั้งค่า Logrotate..."
sudo bash -c "cat <<EOF > /etc/logrotate.d/$SERVICE_NAME
/var/log/journal/*/*.journal {
    daily
    rotate 7
    size 100M
    compress
    delaycompress
}
EOF"

echo "🔄 กำลังเริ่มระบบ (Reloading Systemd)..."
sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME
sudo systemctl restart $SERVICE_NAME

echo "================================================================="
echo "✅ [SUCCESS] แก้ไขปัญหาช่องว่างในชื่อโฟลเดอร์เรียบร้อยแล้ว!"
echo "-----------------------------------------------------------------"
echo "📊 ตรวจสอบสถานะ: sudo systemctl status $SERVICE_NAME"
echo "📡 ดูการเทรดสดๆ: journalctl -u $SERVICE_NAME -f"
echo "================================================================="
