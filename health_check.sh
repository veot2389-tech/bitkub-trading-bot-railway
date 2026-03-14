#!/bin/bash
# บันทึกเป็น health_check.sh
# วิธีใช้: ./health_check.sh https://your-app-name.onrender.com

URL=$1
if [ -z "$URL" ]; then
    echo "❌ กรุณาระบุ URL ของบอท"
    exit 1
fi

echo "🔍 กำลังตรวจสอบสถานะบอทที่ $URL/health ..."
RESPONSE=$(curl -s "$URL/health")

if [[ $RESPONSE == *"healthy"* ]]; then
    echo "✅ บอททำงานปกติ! (Healthy)"
    echo "📄 ข้อมูลตอบกลับ: $RESPONSE"
else
    echo "❌ บอทมีปัญหา หรือยังไม่พร้อมใช้งาน"
    echo "📄 ข้อมูลตอบกลับ: $RESPONSE"
fi
