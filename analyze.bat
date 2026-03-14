@echo off
cd /d "C:\Users\Asus\Desktop\Api sever"
wsl bash -c "cd '/mnt/c/Users/Asus/Desktop/Api sever' && source venv/bin/activate && python3 analyze_csv_linux.py" > analysis_report.txt 2>&1
