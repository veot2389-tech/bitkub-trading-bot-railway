"""
🚚 สร้างคำสั่ง SQL จากข้อมูลเก่าในเครื่อง
แล้วเอาไปวางใน Supabase SQL Editor ได้เลย!
"""
import sqlite3
import os

LOCAL_DBS = ["trading_v8.db", "bot_state.db", "bot_stats.db"]
OUTPUT_FILE = "import_to_supabase.sql"

def escape_sql(val):
    if val is None: return "NULL"
    if isinstance(val, (int, float)): return str(val)
    return "'" + str(val).replace("'", "''") + "'"

def main():
    sql_lines = []
    sql_lines.append("-- 🚚 Auto-generated: Import old data to Supabase")
    sql_lines.append("-- วางใน Supabase SQL Editor แล้วกด Run\n")

    # === LAYERS ===
    for db_path in LOCAL_DBS:
        if not os.path.exists(db_path): continue
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute("SELECT * FROM layers").fetchall()
        except:
            conn.close()
            continue
        conn.close()
        if not rows: continue

        sql_lines.append(f"-- === LAYERS จาก {db_path} ({len(rows)} รายการ) ===")
        for r in rows:
            d = dict(r)
            coin = escape_sql(d.get("coin", "BTC"))
            price = d.get("price", 0)
            amount = d.get("amount", 0)
            if price and amount:
                sql_lines.append(f"INSERT INTO layers (coin, price, amount) VALUES ({coin}, {price}, {amount});")
        sql_lines.append("")
        print(f"✅ Layers: {len(rows)} รายการจาก {db_path}")
        break

    # === TRADES ===
    for db_path in LOCAL_DBS:
        if not os.path.exists(db_path): continue
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute("SELECT * FROM trades").fetchall()
        except:
            conn.close()
            continue
        conn.close()
        if not rows: continue

        sql_lines.append(f"-- === TRADES จาก {db_path} ({len(rows)} รายการ) ===")
        for r in rows:
            d = dict(r)
            coin = escape_sql(d.get("coin", "BTC"))
            side = escape_sql(d.get("side", "BUY"))
            price = d.get("price", 0)
            amount = d.get("amount", d.get("qty", 0))
            profit = d.get("profit", d.get("net_profit", 0))
            ts = d.get("ts", d.get("timestamp", None))
            if ts:
                sql_lines.append(f"INSERT INTO trades (coin, side, price, amount, profit, ts) VALUES ({coin}, {side}, {price}, {amount}, {profit}, {escape_sql(ts)});")
            else:
                sql_lines.append(f"INSERT INTO trades (coin, side, price, amount, profit) VALUES ({coin}, {side}, {price}, {amount}, {profit});")
        sql_lines.append("")
        print(f"✅ Trades: {len(rows)} รายการจาก {db_path}")
        break

    # === DAILY SNAPSHOTS ===
    for db_path in LOCAL_DBS:
        if not os.path.exists(db_path): continue
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute("SELECT * FROM daily_snapshots").fetchall()
        except:
            conn.close()
            continue
        conn.close()
        if not rows: continue

        sql_lines.append(f"-- === SNAPSHOTS จาก {db_path} ({len(rows)} รายการ) ===")
        for r in rows:
            d = dict(r)
            ts = escape_sql(d.get("ts"))
            equity = d.get("total_equity", 0)
            profit = d.get("today_profit", 0)
            thb = d.get("balance_thb", 0)
            sql_lines.append(f"INSERT INTO daily_snapshots (ts, total_equity, today_profit, balance_thb) VALUES ({ts}, {equity}, {profit}, {thb}) ON CONFLICT (ts) DO NOTHING;")
        sql_lines.append("")
        print(f"✅ Snapshots: {len(rows)} รายการจาก {db_path}")
        break

    # เขียนไฟล์
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(sql_lines))

    print(f"\n🎉 สร้างไฟล์ {OUTPUT_FILE} เรียบร้อย!")
    print(f"📋 ขั้นตอนถัดไป:")
    print(f"   1. เปิดไฟล์ {OUTPUT_FILE}")
    print(f"   2. ก๊อปเนื้อหาทั้งหมด")
    print(f"   3. วางใน Supabase SQL Editor แล้วกด Run")

if __name__ == "__main__":
    main()
