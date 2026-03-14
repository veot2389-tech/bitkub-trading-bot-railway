#!/bin/bash

# =================================================================
# 🚀 Turbo DGT v8.8 - Unified Installer (Space-Safe & Stable)
# =================================================================

PROJECT_DIR=$(pwd)
SERVICE_NAME="turbodgt"
USER_NAME=$USER

echo "🧹 [1/3] กำลังเตรียมสคริปต์ช่วยรัน (Space-Safe Launcher)..."

# สร้างสคริปต์ช่วยรันเพื่อตัดปัญหาเรื่องช่องว่างใน Path
cat <<EOF > run_bot.sh
#!/bin/bash
cd "$(pwd)"
if [ -d "venv" ]; then
    source venv/bin/activate
fi
exec python3 trading_bot_v8.py
EOF
chmod +x run_bot.sh

echo "⚙️ [2/3] อัปเดต Systemd Service..."
sudo bash -c "cat <<EOF > /etc/systemd/system/$SERVICE_NAME.service
[Unit]
Description=Turbo DGT v8.8 Mathematical Trading Bot
After=network.target

[Service]
Type=simple
User=$USER_NAME
WorkingDirectory=$PROJECT_DIR
ExecStart=$PROJECT_DIR/run_bot.sh
Restart=always
RestartSec=5
LimitNOFILE=65536
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF"

echo "🔄 [3/3] ระบบกำลังเริ่มทำงานใหม่..."
sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME
sudo systemctl restart $SERVICE_NAME

echo "================================================================="
echo "✅ [DONE] แก้ไขจุดค้างเรียบร้อยแล้ว!"
echo "📡 ตรวจสอบ Log: journalctl -u $SERVICE_NAME -f"
echo "================================================================="
