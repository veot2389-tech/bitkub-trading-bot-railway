import os
import glob

# Files to keep
KEEP = ['trading_bot_v8.py', 'bitkub_async.py', 'config.json', '.env', 'README.md', 'PROJECT_STRUCTURE.md', 'history.json', 'trading_v8.db', 'analyze_v8.py', 'start.sh', 'run_bot.sh', 'restart_bot.sh', 'txn_report_189497_1773465379.csv', 'ws_topics.txt', 'bot_output.log', 'turbodgt.service.backup', 'ปิดตัวที่รันอยู่ทั้งหมด.txt', 'หยุดระบบ Systemd ก่อน.txt']

patterns = ['*.py', '*.sh', '*.bat', '*.txt', '*.json', 'out_*', 'analysis_*', 'report_*']

for p in patterns:
    for f in glob.glob(p):
        if f not in KEEP and not os.path.isdir(f):
            try:
                os.remove(f)
                print(f"Deleted: {f}")
            except Exception as e:
                print(f"Failed to delete {f}: {e}")
