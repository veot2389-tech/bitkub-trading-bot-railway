#!/bin/bash
PROJECT_DIR=$(pwd)
USER_NAME=$(whoami)
LINK_NAME="/home/asus/bitkub_v8"

echo "🔗 สร้างทางลัดระบบ (Creating Symlink to avoid spaces)..."
# ลบทางลัดเก่า (ถ้ามี) และสร้างใหม่
rm -f "$LINK_NAME"
ln -s "$PROJECT_DIR" "$LINK_NAME"

echo "🔧 กำลังซ่อมแซมเส้นทางระบบ (Symlink Method)..."

# Create the service file using the Link path
cat <<SERVICE > turbodgt.service.tmp
[Unit]
Description=Turbo DGT v8.8 Trading Bot
After=network.target

[Service]
ExecStart="$LINK_NAME/venv/bin/python3" "$LINK_NAME/trading_bot_v8.py"
WorkingDirectory=$LINK_NAME
StandardOutput=inherit
StandardError=inherit
Restart=always
RestartSec=10
User=$USER_NAME
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
SERVICE

# Move and Restart
sudo mv turbodgt.service.tmp /etc/systemd/system/turbodgt.service
sudo systemctl daemon-reload
sudo systemctl restart turbodgt

echo "✅ ซ่อมแซมเรียบร้อยด้วยวิธี Symlink! ลองเช็คสถานะอีกครั้งครับ"
