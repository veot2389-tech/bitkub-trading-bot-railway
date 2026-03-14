# 🦅 Turbo DGT v8.8 - Project Structure

โครงสร้างไฟล์และรายละเอียดหน้าที่ของระบบเทรดอัตโนมัติ Turbo DGT v8.8

## 📂 รายละเอียดโครงสร้างไฟล์ (Internal File Mapping)

### 🧠 Core Logic (ส่วนการทำงานหลัก)
- **`trading_bot_v8.py`**: สมองกลหลัก ควบคุม Logic ทั้งหมด (WebSocket, Trading Logic, Database Sync, Telegram API)
- **`bitkub_async.py`**: Driver สำหรับเชื่อมต่อ Bitkub API v3 (Async) พร้อมระบบจัดการความปลอดภัยและ Clean Amount
- **`analyze_v8.py`**: วิเคราะห์ข้อมูลจาก DB เพื่อสรุป Win Rate, กำไรรายเหรียญ และประสิทธิภาพระบบ

### ⚙️ Configuration & Data (การตั้งค่าและข้อมูล)
- **`config.json`**: เก็บ API Key, Secret, Token และ Grid Step (Fibonacci Base)
- **`trading_v8.db`**: ฐานข้อมูล SQLite3 เก็บตาราง `trades`, `layers`, และ `snapshots`
- **`history.json`**: เก็บประวัติราคา 30 จุดย้อนหลัง เพื่อใช้คำนวณ Z-Score เมื่อบอท Restart
- **`ws_topics.txt`**: ข้อมูล Log และ Topic สำหรับการเชื่อมต่อ WebSocket

### 🚀 Shell Scripts & Automation (ระบบควบคุม)
- **`start.sh`**: สคริปต์เริ่มต้นระบบ เคลียร์ Process เก่าและสั่งรันบอท
- **`run_bot.sh`**: ตัวขับเคลื่อน (Launcher) จัดการ Absolute Path สำหรับ Systemd
- **`fix_all.sh`**: สคริปต์ซ่อมแซมระบบ ติดตั้ง Library และตั้งค่า Service อัตโนมัติ
- **`setup_systemd.sh`**: ติดตั้งบอทเป็น Background Service บน Linux/WSL

### 🛠️ Debug & Utilities (เครื่องมือตรวจสอบ)
- **`check_profit_v8.py`**: ตรวจสอบผลกำไรแยกตามช่วงเวลา
- **`debug_balances.py`**: เช็คยอดเงินจริงในบัญชี Bitkub
- **`debug_db.py`**: ตรวจสอบความถูกต้องของข้อมูลในฐานข้อมูล
- **`debug_ws.py`**: ทดสอบการรับสัญญาณราคาจาก WebSocket

### 📄 Documentation (เอกสาร)
- **`README.md`**: คู่มือหลัก อธิบายอัลกอริทึม Fibonacci, Z-Score และ Momentum
- **`PROJECT_STRUCTURE.md`**: เอกสารฉบับนี้ (โครงสร้างไฟล์)
- **`ปิดตัวที่รันอยู่ทั้งหมด.txt`**: คำสั่งด่วนสำหรับหยุดการทำงาน
- **`หยุดระบบ Systemd ก่อน.txt`**: ขั้นตอนการหยุด Service อย่างถูกวิธี

---

## 🧠 อัลกอริทึมที่สำคัญ (Mathematical Core)
1. **Dynamic Fibonacci Grid**: ระยะห่างไม้ขยายตามเลข Fibonacci เพื่อลดความเสี่ยง
2. **Probability Filters**: 
   - **Z-Score**: ป้องกันการซื้อที่จุดสูงสุด (Overbought)
   - **Momentum Slope**: ป้องกันการช้อน "มีดร่วง" (Downtrend)
3. **0.6% Net Profit Rule**: บอทจะขายเมื่อกำไรสุทธิ (หลังหักค่าธรรมเนียม) >= 0.6% เท่านั้น
4. **Dynamic Slot Management**: คำนวณขนาดไม้จาก Total Equity (Asset + THB) อัตโนมัติ

---
*จัดทำโดย Gemini CLI - ระบบจัดการโปรเจคอัจฉริยะ*
