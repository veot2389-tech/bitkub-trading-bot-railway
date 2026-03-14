#!/bin/bash

# Get the absolute path of the current directory
PROJECT_DIR=$(pwd)
SERVICE_NAME="turbodgt"
PYTHON_BIN=$(which python3)

# If venv exists, use it
if [ -d "$PROJECT_DIR/venv" ]; then
    PYTHON_BIN="$PROJECT_DIR/venv/bin/python3"
fi

echo "🚀 [SYSTEMD SETUP] กำลังสร้างไฟล์ Service สำหรับ Ubuntu..."

# Create the service file
sudo bash -c "cat <<EOF > /etc/systemd/system/$SERVICE_NAME.service
[Unit]
Description=Turbo DGT v8.8 Trading Bot
After=network.target

[Service]
WorkingDirectory=$PROJECT_DIR
ExecStart=$PYTHON_BIN trading_bot_v8.py
Restart=always
RestartSec=10
User=$USER
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF"

# Reload and start
echo "📡 [SYSTEMD] Reloading daemon..."
sudo systemctl daemon-reload
echo "🟢 [SYSTEMD] Enabling $SERVICE_NAME..."
sudo systemctl enable $SERVICE_NAME
echo "🚀 [SYSTEMD] Starting $SERVICE_NAME..."
sudo systemctl restart $SERVICE_NAME

echo "✅ [SUCCESS] บอทรันในฐานะ Systemd Service เรียบร้อยแล้ว!"
echo "📍 คุณสามารถเช็คสถานะได้ด้วยคำสั่ง: sudo systemctl status $SERVICE_NAME"
echo "📜 ดู Log สดๆ ได้ด้วยคำสั่ง: journalctl -u $SERVICE_NAME -f"
