import sqlite3
import os

try:
    conn = sqlite3.connect("trading_v8.db")
    c = conn.cursor()
    with open("db_out.txt", "w", encoding="utf-8") as f:
        f.write("--- RECENT TRADES ---\n")
        c.execute("SELECT datetime(ts, '+7 hours'), coin, side, price, amount, profit FROM trades ORDER BY ts DESC LIMIT 15")
        rows = c.fetchall()
        for r in rows:
            f.write(str(r) + "\n")

        f.write("\n--- DAILY SNAPSHOTS ---\n")
        c.execute("SELECT * FROM daily_snapshots ORDER BY ts DESC LIMIT 5")
        snaps = c.fetchall()
        for s in snaps:
            f.write(str(s) + "\n")
    conn.close()
    print("DONE")
except Exception as e:
    with open("db_out.txt", "w", encoding="utf-8") as f:
        f.write("ERROR: " + str(e))
