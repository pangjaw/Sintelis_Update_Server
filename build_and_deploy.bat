@echo off
title Build and Deploy Sintelis Utility
set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%01_scripts_pendukung"
echo Menjalankan build and deploy...
python build_release.py
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Build gagal!
    pause
    exit /b %ERRORLEVEL%
)

echo Merestart Update Server...
set "SERVER_DIR=%ROOT_DIR%02_server_update"
wscript.exe "%SERVER_DIR%\run_update_server.vbs"
echo [SUKSES] Build dan rilis berhasil diterapkan!
pause
