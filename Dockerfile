# ใช้ Debian-based slim image (มาตรฐาน Linux)
FROM python:3.11-slim

# ตั้งค่า Working Directory
WORKDIR /app

# ติดตั้ง System Packages (สำหรับ Postgres และเครื่องมือ Linux พื้นฐาน)
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# คัดลอกและติดตั้ง Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# คัดลอกโค้ดทั้งหมด
COPY . .

# ให้สิทธิ์การรันสำหรับสคริปต์ .sh (ถ้ามี)
RUN if ls *.sh 1> /dev/null 2>&1; then chmod +x *.sh; fi
# ตั้งค่า Environment สำหรับ Linux Production
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PORT=8080

# Expose พอร์ตมาตรฐาน (Render ใช้ค่าจาก ENV $PORT)
EXPOSE 8080

# คำสั่งรันบอท (Linux Style)
CMD ["python3", "-u", "trading_bot_v8_render.py"]
