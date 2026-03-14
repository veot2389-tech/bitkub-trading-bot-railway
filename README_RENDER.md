# 🚀 วิธี Deploy Turbo DGT บน Render (Free Tier)

### 1. เตรียม Supabase
1. สร้างโปรเจกต์ใน [Supabase](https://supabase.com/)
2. ก๊อปปี้ **Connection string (URI)** จาก Settings > Database (ใช้พอร์ต 6543)

### 2. ตั้งค่าบน Render
1. สมัคร/ล็อกอิน [Render](https://render.com/)
2. สร้าง **New Web Service** และเชื่อมต่อกับ GitHub Repo ของคุณ
3. เลือก **Runtime: Docker** (หรือ Python ก็ได้ แต่ Docker จะเสถียรกว่า)
4. ไปที่แถบ **Environment** และเพิ่มค่าเหล่านี้:
   * `DATABASE_URL`: (จาก Supabase)
   * `API_KEY`: (จาก Bitkub)
   * `API_SECRET`: (จาก Bitkub)
   * `TELEGRAM_TOKEN`: (จาก Telegram)
   * `TELEGRAM_CHAT_ID`: (ID ของคุณ)

### 3. วิธีป้องกัน Bot หลับ (Keep Alive)
เนื่องจาก Render Free Tier จะปิดตัวเองถ้าไม่มีคนเข้าเว็บ:
1. ไปที่ [cron-job.org](https://cron-job.org/)
2. สร้าง Job ใหม่ให้ยิงไปที่ URL ของคุณ (เช่น `https://your-bot.onrender.com/health`) ทุกๆ 5-10 นาที
3. วิธีนี้จะทำให้ Bot ของคุณรันได้ตลอด 24 ชม. ฟรีๆ!

### 4. ตรวจสอบสถานะ
* คุณสามารถเช็คได้ที่ `https://your-bot.onrender.com/health` ถ้าขึ้น `healthy` แสดงว่าบอททำงานปกติครับ
