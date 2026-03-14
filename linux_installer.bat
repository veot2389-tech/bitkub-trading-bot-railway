@echo off
setlocal
cd /d "C:\Users\Asus\Desktop\Api sever"
wsl bash -c "cd '/mnt/c/Users/Asus/Desktop/Api sever' && ./venv/bin/pip install pandas-ta loguru python-dotenv"
wsl bash -c "cd '/mnt/c/Users/Asus/Desktop/Api sever' && ./venv/bin/python3 analyze_v8.py" > analysis_v8_result.txt
endlocal
