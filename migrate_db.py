import sqlite3
import os

OLD_DB = "trading_v8.db"
DB_STATS = "bot_stats.db"
DB_STATE = "bot_state.db"

if not os.path.exists(OLD_DB):
    print(f"❌ ไม่พบไฟล์ {OLD_DB} ไม่ต้องย้ายข้อมูล")
    exit()

print(f"📦 เริ่มการย้ายข้อมูลจาก {OLD_DB}...")

# 1. ย้ายไป bot_stats.db (trades, daily_snapshots)
conn_old = sqlite3.connect(OLD_DB)
c_old = conn_old.cursor()

conn_stats = sqlite3.connect(DB_STATS)
c_stats = conn_stats.cursor()
c_stats.execute('''CREATE TABLE IF NOT EXISTS trades 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, coin TEXT, side TEXT, price REAL, amount REAL, profit REAL, ts DATETIME)''')
c_stats.execute('''CREATE TABLE IF NOT EXISTS daily_snapshots 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, ts DATE UNIQUE, total_equity REAL, today_profit REAL, balance_thb REAL)''')

c_old.execute("SELECT coin, side, price, amount, profit, ts FROM trades")
trades = c_old.fetchall()
c_stats.executemany("INSERT INTO trades (coin, side, price, amount, profit, ts) VALUES (?, ?, ?, ?, ?, ?)", trades)

try:
    c_old.execute("SELECT ts, total_equity, today_profit, balance_thb FROM daily_snapshots")
    snapshots = c_old.fetchall()
    c_stats.executemany("INSERT OR REPLACE INTO daily_snapshots (ts, total_equity, today_profit, balance_thb) VALUES (?, ?, ?, ?)", snapshots)
except: pass

conn_stats.commit()
conn_stats.close()
print(f"✅ ย้ายสถิติไป {DB_STATS} เรียบร้อย")

# 2. ย้ายไป bot_state.db (layers)
conn_state = sqlite3.connect(DB_STATE)
c_state = conn_state.cursor()
c_state.execute('''CREATE TABLE IF NOT EXISTS layers (coin TEXT, price REAL, amount REAL)''')

c_old.execute("SELECT coin, price, amount FROM layers")
layers = c_old.fetchall()
c_state.executemany("INSERT INTO layers (coin, price, amount) VALUES (?, ?, ?)", layers)

conn_state.commit()
conn_state.close()
print(f"✅ ย้ายสถานะปัจจุบันไป {DB_STATE} เรียบร้อย")

conn_old.close()

# สำรองไฟล์เก่า
os.rename(OLD_DB, OLD_DB + ".bak")
print(f"♻️ สำรองไฟล์เก่าเป็น {OLD_DB}.bak")
