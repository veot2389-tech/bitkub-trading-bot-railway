import sqlite3
import pandas as pd
from datetime import datetime
import os

db_path = "trading_v8.db"

def analyze_performance():
    if not os.path.exists(db_path):
        print("Database not found.")
        return

    conn = sqlite3.connect(db_path)
    
    # 1. Trade History Analysis
    df = pd.read_sql_query("SELECT * FROM trades", conn)
    if df.empty:
        print("No trade history available yet.")
        conn.close()
        return

    df['ts'] = pd.to_datetime(df['ts'])
    
    print("\n" + "="*50)
    print(f"📊 TURBO DGT v8.8 PERFORMANCE ANALYSIS")
    print(f"Update Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*50)

    # Calculate metrics
    sells = df[df['side'] == 'SELL']
    buys = df[df['side'] == 'BUY']
    
    total_profit = sells['profit'].sum()
    win_rate = 100 # In grid trading, every sell is usually a win
    
    print(f"💰 Total Realized Profit: {total_profit:,.2f} THB")
    print(f"🔄 Total Completed Cycles: {len(sells)} trades")
    print(f"🎯 Total Open Positions: {len(buys) - len(sells)} layers")
    
    # Per Coin Analysis
    print("\n📈 PERFORMANCE BY COIN:")
    coin_stats = sells.groupby('coin')['profit'].agg(['sum', 'count']).sort_values(by='sum', ascending=False)
    print(coin_stats.rename(columns={'sum': 'Profit (THB)', 'count': 'Trade Count'}))

    # Portfolio Growth (Daily Snapshots)
    print("\n📉 PORTFOLIO GROWTH (Daily Snapshots):")
    try:
        snapshots = pd.read_sql_query("SELECT * FROM daily_snapshots ORDER BY ts DESC LIMIT 7", conn)
        if not snapshots.empty:
            print(snapshots[['ts', 'total_equity', 'today_profit']].to_string(index=False))
        else:
            print("(No snapshots recorded yet. Recording starts today.)")
    except:
        print("(Daily snapshot table is being initialized...)")

    conn.close()
    print("\n" + "="*50)

if __name__ == "__main__":
    analyze_performance()
