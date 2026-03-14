#!/bin/bash
cd "/mnt/c/Users/Asus/Desktop/Api sever"
source venv/bin/activate

# Install pandas if missing, and remove bad packages if any
pip install pandas > /dev/null 2>&1

cat << 'EOF' > analyze_csv_linux.py
import pandas as pd
import sys

try:
    df = pd.read_csv('txn_report_189497_1773465379.csv', skiprows=1)
    buys = df[(df['Currency'] == 'THB') & (df['Type'] == 'buy')]
    sells = df[(df['Currency'] == 'THB') & (df['Type'] == 'sell')]
    fees = df[df['Type'] == 'fee']
    
    spent = abs(buys['Amount'].sum() if not buys.empty else 0)
    received = sells['Amount'].sum() if not sells.empty else 0
    total_fees = abs(fees['Amount'].sum() if not fees.empty else 0)
    num_sells = len(sells)
    
    print("\n" + "="*40)
    print("📊 รายงานวิเคราะห์การเทรดจาก Bitkub 📊")
    print("="*40)
    print(f"🔴 เงินบาทที่ใช้ไป (Total THB Spent)     : {spent:,.2f} บาท")
    print(f"🟢 เงินบาทที่ได้มา (Total THB Received)  : {received:,.2f} บาท")
    print(f"💸 ค่าธรรมเนียมรวม (Total Trading Fees)  : {total_fees:,.3f} บาท")
    print("-" * 40)
    print(f"🎯 จำนวนครั้งที่ 'ขายทำกำไร' สำเร็จ     : {num_sells} ครั้ง")
    net_flow = received - spent - total_fees
    status_emoji = "🔥" if net_flow > 0 else "🛍️"
    print(f"{status_emoji} กระแสเงินสดสุทธิ (Net Cash Flow)      : {net_flow:,.2f} บาท")
    print("="*40)
    print("*หมายเหตุ: Net Flow ติดลบ ไม่ได้แปลว่าขาดทุน \nแต่หมายถึงเงินบาทถูกเปลี่ยนสถานะไปเป็น 'เหรียญ (Assets)' ที่กำลังถือรอขายอยู่ในขณะนี้ครับ*")
    print("="*40 + "\n")

except Exception as e:
    print(f"Error: {e}")
EOF

python3 analyze_csv_linux.py
