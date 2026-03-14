# 🚀 ขั้นตอนการ Deploy Turbo DGT บน Railway + Supabase

### 1. เตรียมฐานข้อมูลบน Supabase
1. ไปที่ [Supabase](https://supabase.com/) สร้าง Project ใหม่
2. ไปที่ **Project Settings** > **Database**
3. คัดลอก **Connection string** ในรูปแบบ **URI** (Transaction Mode พอร์ต 6543)
   * ตัวอย่าง: `postgresql://postgres:[PASSWORD]@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres`

### 2. ตั้งค่าบน Railway
1. เชื่อมต่อ GitHub Repo กับ [Railway](https://railway.app/)
2. ไปที่แผง **Variables** และเพิ่มค่าดังนี้:
   * `DATABASE_URL`: (URI ที่ก๊อปมาจาก Supabase)
   * `API_KEY`: (Bitkub API Key)
   * `API_SECRET`: (Bitkub API Secret)
   * `TELEGRAM_TOKEN`: (Token จาก BotFather)
   * `TELEGRAM_CHAT_ID`: (ID ของคุณ)
   * `PORT`: `8080` (Railway จะจัดการให้เอง แต่ใส่ไว้กันพลาด)

### 3. ตั้งค่าความเสถียร (Settings)
1. ไปที่ **Settings** > **Healthcheck**
2. ใส่ Path เป็น `/health`
3. Railway จะใช้พอร์ตนี้ตรวจสอบว่า Bot ของคุณยังทำงานอยู่หรือไม่

### 4. หมายเหตุสำคัญ
* ไฟล์โค้ดหลักสำหรับรันบน Cloud คือ `trading_bot_v8_railway.py`
* ระบบจะสร้างตารางใน Supabase ให้โดยอัตโนมัติเมื่อเริ่มรันครั้งแรก
* ข้อมูลประวัติการเทรดและ "ไม้" (Layers) จะถูกเก็บไว้อย่างถาวรใน Supabase
