import sqlite3
import os

db_path = "/home/asus/bitkub_v8/trading_v8.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    print("--- 5 Latest SOL Trades ---")
    c.execute("SELECT * FROM trades WHERE coin='SOL' ORDER BY id DESC LIMIT 5")
    rows = c.fetchall()
    for row in rows:
        print(row)
    conn.close()
else:
    print(f"Database not found at {db_path}")
