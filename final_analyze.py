import pandas as pd
import json

try:
    df = pd.read_csv('txn_report_189497_1773465379.csv', skiprows=1)
    buys = df[(df['Currency'] == 'THB') & (df['Type'] == 'buy')]['Amount'].abs().sum()
    sells = df[(df['Currency'] == 'THB') & (df['Type'] == 'sell')]['Amount'].sum()
    fees = df[df['Type'] == 'fee']['Amount'].abs().sum()
    num_sells = len(df[df['Type'] == 'sell']) // 2
    
    res = {
        "spent": float(buys),
        "received": float(sells),
        "fees": float(fees),
        "count": int(num_sells),
        "net": float(sells - buys - fees)
    }
    with open('final_results.json', 'w') as f:
        json.dump(res, f)
except Exception as e:
    with open('final_results.json', 'w') as f:
        json.dump({"error": str(e)}, f)
