#!/bin/bash
# Create a symlink to avoid space issues in commands
PROJECT_DIR="/mnt/c/Users/Asus/Desktop/Api sever"
SYMLINK="/tmp/apisever"
rm -f "$SYMLINK"
ln -s "$PROJECT_DIR" "$SYMLINK"

cd "$SYMLINK"
source venv/bin/activate

# Execute the analysis
python3 final_analyze.py

# Install useful packages
pip install pandas-ta loguru python-dotenv

# Clean up temporary scripts created during debugging
rm -f check_db_history.py check_sol.py debug_balances.py debug_db.py debug_ws.py dump_db.py
rm -f run_chk.sh run_analyze.sh run_csv.sh final_analyze.py analyze.bat
rm -f out_*.txt analysis_*.txt report_out.txt db_out.txt

echo "CLEANUP_AND_UPGRADE_DONE"
