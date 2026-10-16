@echo off
title Build and Deploy Sintelis Utility
cd /d "C:\Users\SINTEL 1.21 BOO\Documents\Server\Sintelis_Update_Server\01_scripts_pendukung"
echo Menjalankan build and deploy...
python build_release.py
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Build gagal!
    pause
    exit /b %ERRORLEVEL%
)

echo Merestart Update Server...
powershell -Command "$p = [wmiclass]'Win32_Process'; $p.Create('C:\Users\SINTEL 1.21 BOO\AppData\Local\Programs\Python\Python314\python.exe "C:\Users\SINTEL 1.21 BOO\Documents\Server\Sintelis_Update_Server\02_server_update\server_update.py"', 'C:\Users\SINTEL 1.21 BOO\Documents\Server\Sintelis_Update_Server\02_server_update', $null)"
echo [SUKSES] Build dan rilis berhasil diterapkan!
pause
