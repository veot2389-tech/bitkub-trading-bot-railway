#!/bin/bash
PROJECT_DIR=$(pwd)
SERVICE_NAME="turbodgt"

# 1. สร้างตัวช่วยรัน
cat <<LAUNCH > run_bot.sh
#!/bin/bash
cd "$PROJECT_DIR"
if [ -d "venv" ]; then
    source venv/bin/activate
fi
exec python3 trading_bot_v8.py
LAUNCH
chmod +x run_bot.sh

# 2. แก้ปัญหาทางเทคนิคเรื่องช่องว่าง
sudo bash -c "cat <<SERVICE > /etc/systemd/system/$SERVICE_NAME.service
[Unit]
Description=Turbo DGT v8.8 Trading Bot
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=\"$PROJECT_DIR\"
ExecStart=\"$PROJECT_DIR/run_bot.sh\"
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
SERVICE"

# 3. รันระบบใหม่
sudo systemctl daemon-reload
sudo systemctl restart $SERVICE_NAME
echo "================================================="
echo "✅ แก้ไขสำเร็จ! บอทเริ่มทำงานแล้ว"
echo "================================================="
