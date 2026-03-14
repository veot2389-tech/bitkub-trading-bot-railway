import sqlite3
from datetime import datetime

conn = sqlite3.connect("trading_v8.db")
c = conn.cursor()

print("--- RECENT TRADES ---")
c.execute("SELECT id, coin, side, price, amount, profit, ts FROM trades ORDER BY ts DESC LIMIT 15")
rows = c.fetchall()
for r in rows:
    print(r)

print("\n--- DAILY SNAPSHOTS ---")
c.execute("SELECT * FROM daily_snapshots ORDER BY ts DESC LIMIT 5")
snaps = c.fetchall()
for s in snaps:
    print(s)

conn.close()
