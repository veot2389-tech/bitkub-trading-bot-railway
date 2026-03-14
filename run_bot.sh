#!/bin/bash
# บังคับเข้าโฟลเดอร์โครงการ (ใช้เครื่องหมายอัญประกาศครอบช่องว่างไว้)
cd "/mnt/c/Users/Asus/Desktop/Api sever"
if [ -d "venv" ]; then
    source venv/bin/activate
fi
exec python3 trading_bot_v8.py "$@"
