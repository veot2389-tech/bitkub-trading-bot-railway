import sqlite3
from datetime import datetime

def check_summary():
    try:
        conn = sqlite3.connect("trading_v8.db")
        c = conn.cursor()

        print("\n" + "="*40)
        print("📊 TURBO DGT v8.0 - PROFIT REPORT")
        print("="*40)

        # 1. สรุปกำไรรวม
        c.execute("SELECT SUM(profit), COUNT(id) FROM trades WHERE side='SELL'")
        total_profit_thb, trade_count = c.fetchone()
        
        if trade_count > 0:
            print(f"💰 Total Successful Trades: {trade_count} times")
            print(f"📈 Total Profit: {total_profit_thb:,.2f} THB")
            print(f"📈 Avg. Profit per Trade: {total_profit_thb/trade_count:,.2f} THB")
        else:
            print("⏳ No sell trades recorded yet.")

        # 2. ดูเหรียญที่ทำเงินมากที่สุด
        print("\nTOP PERFORMING COINS:")
        c.execute("SELECT coin, COUNT(id) as count FROM trades WHERE side='SELL' GROUP BY coin ORDER BY count DESC")
        for coin, count in c.fetchall():
            print(f" - {coin}: {count} times")

        # 3. ดูไม้ที่ค้างอยู่ (Inventory/Layers)
        print("\n📦 CURRENT HOLDINGS (LAYERS):")
        c.execute("SELECT coin, price FROM layers")
        layers = c.fetchall()
        if layers:
            current_coin = ""
            for coin, price in layers:
                if coin != current_coin:
                    print(f" [{coin}]")
                    current_coin = coin
                print(f"  └─ Buy Price: {price:,.4f}")
        else:
            print("  (No active layers)")

        print("="*40)
        conn.close()
    except Exception as e:
        print(f"❌ Error reading database: {e}")
        print("Tip: Make sure the bot has started trading to create the database file.")

if __name__ == "__main__":
    check_summary()
