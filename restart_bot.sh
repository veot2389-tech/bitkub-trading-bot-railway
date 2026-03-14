#!/bin/bash
cd "/mnt/c/Users/Asus/Desktop/Api sever"
pkill -f trading_bot_v8.py 2>/dev/null
sleep 1
if [ -d "venv" ]; then
    source venv/bin/activate
fi
python3 trading_bot_v8.py
sleep 3
echo "PID:"
pgrep -f trading_bot_v8.py
echo "---LOG---"
tail -10 bot_output.log
