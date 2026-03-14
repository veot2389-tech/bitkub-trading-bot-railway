#!/bin/bash

# --- Turbo DGT Start Script for Linux/Render ---

echo "🚀 [SYSTEM] Starting Turbo DGT Render Lite..."

# 1. ตรวจสอบ Environment Variables เบื้องต้น
if [ -z "$DATABASE_URL" ]; then
    echo "❌ [ERROR] DATABASE_URL is not set!"
    exit 1
fi

# 2. รันบอทโดยใช้ Python 3 (Render ใช้โครงสร้าง Linux)
# ใช้ -u เพื่อให้ Log แสดงผลทันที (Unbuffered)
python3 -u trading_bot_v8_render.py
