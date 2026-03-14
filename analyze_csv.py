import pandas as pd

# Load the CSV file
df = pd.read_csv('txn_report_189497_1773465379.csv', skiprows=1) # Skip the 'name' row

# Convert Date to datetime
df['Date'] = pd.to_datetime(df['Date'])

# Filter only 'sell' transactions
sells = df[df['Type'] == 'sell']

print("--- 📊 Analysis Report from Bitkub CSV ---")

# Calculate Total Sold (Volume) and Net Profit
total_profit_thb = 0
total_fees_thb = 0

print("\n--- Summary by Coin ---")
coins = df['Currency'].unique()
for coin in coins:
    if coin == 'THB': continue
    
    # Get all sell rows for this coin
    coin_sells = sells[sells['Currency'] == coin]
    # In Bitkub CSV, the row after a 'sell' of a coin is usually the THB received.
    # We can match by TXID to find the THB received and the fee.
    
    coin_profit = 0
    sell_txids = coin_sells['TXID'].unique()
    
    for txid in sell_txids:
        # Get all rows for this specific transaction ID
        tx_rows = df[df['TXID'] == txid]
        
        # Get the THB received for selling
        thb_rows = tx_rows[(tx_rows['Currency'] == 'THB') & (tx_rows['Type'] == 'sell')]
        if not thb_rows.empty:
            received_thb = thb_rows.iloc[0]['Amount']
            
            # Find the corresponding buy cost (approximate mapping or total matched PnL isn't fully in CSV)
            # But we can calculate total fees paid for sells
            
            # In standard trading, profit = (Sell THB) - (Buy THB) - (Fees)
            # Since CSV doesn't link buys to sells, we'll just sum volumes and fees.
            pass

print("\n--- 💸 Trading Fees Paid (Total) ---")
fees_df = df[df['Type'] == 'fee']
total_fees = fees_df['Amount'].sum()
print(f"Total Fees Paid: {abs(total_fees):.2f} THB")

print("\n--- 💰 Total THB Spent & Received ---")
thb_buys = df[(df['Currency'] == 'THB') & (df['Type'] == 'buy')]
thb_sells = df[(df['Currency'] == 'THB') & (df['Type'] == 'sell')]

total_spent = thb_buys['Amount'].sum()
total_received = thb_sells['Amount'].sum()

print(f"Total THB Spent on Buying: {abs(total_spent):.2f} THB")
print(f"Total THB Received from Selling: {total_received:.2f} THB")
print(f"Net THB Cash Flow (Received - Spent - Fees): {total_received - abs(total_spent) - abs(total_fees):.2f} THB")

print("\n--- 🎯 Total Trades Count ---")
buy_count = len(df[df['Type'] == 'buy']) // 2 # Divide by 2 because each buy has a Coin row and a THB row
sell_count = len(df[df['Type'] == 'sell']) // 2 
print(f"Total Buy Executions: {buy_count}")
print(f"Total Sell Executions: {sell_count}")

