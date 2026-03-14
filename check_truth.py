import sqlite3
import os

def check():
    print("--- 🛠️ CURRENT GRID STATE (bot_state.db) ---")
    if os.path.exists("bot_state.db"):
        conn = sqlite3.connect("bot_state.db")
        c = conn.cursor()
        c.execute("SELECT * FROM layers")
        rows = c.fetchall()
        if rows:
            for r in rows:
                print(f"Coin: {r[0]} | Price: {r[1]:,.2f} | Amount: {r[2]:,.6f}")
        else:
            print("No active layers in DB.")
        conn.close()
    else:
        print("bot_state.db not found.")

    print("\n--- 📊 RECENT TRADES (bot_stats.db) ---")
    if os.path.exists("bot_stats.db"):
        conn = sqlite3.connect("bot_stats.db")
        c = conn.cursor()
        c.execute("SELECT coin, side, price, amount, profit, ts FROM trades ORDER BY id DESC LIMIT 5")
        rows = c.fetchall()
        if rows:
            for r in rows:
                print(f"[{r[5]}] {r[1]} {r[0]} @ {r[2]:,.2f} (Amt: {r[3]:,.6f}, Profit: {r[4]:+.2f} THB)")
        else:
            print("No trades found in DB.")
        conn.close()
    else:
        print("bot_stats.db not found.")

if __name__ == "__main__":
    check()
