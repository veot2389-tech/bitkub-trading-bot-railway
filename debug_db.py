import sqlite3
import os

db_path = r"c:\Users\Asus\Desktop\Api sever\trading_v8.db"
if not os.path.exists(db_path):
    print(f"File not found: {db_path}")
else:
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    print("--- TRADES ---")
    c.execute("SELECT * FROM trades ORDER BY id DESC LIMIT 10")
    for row in c.fetchall():
        print(row)
    
    print("\n--- LAYERS ---")
    c.execute("SELECT * FROM layers")
    for row in c.fetchall():
        print(row)
    conn.close()
