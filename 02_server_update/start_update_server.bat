@echo off
cd /d "%~dp0"
if exist "C:\Users\SINTEL 1.21 BOO\AppData\Local\Programs\Python\Python314\python.exe" (
    "C:\Users\SINTEL 1.21 BOO\AppData\Local\Programs\Python\Python314\python.exe" server_update.py
) else (
    python server_update.py
)
