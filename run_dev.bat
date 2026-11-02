@echo off
title Sintelis Utility (Mode Cepat / Live Python)
set "ROOT_DIR=%~dp0"
cd /d "%ROOT_DIR%01_scripts_pendukung\web-app"
echo ========================================================
echo  Membuka Sintelis Utility Langsung (Tanpa Build PyInstaller)
echo  Perubahan kode langsung aktif dalam 1 detik!
echo ========================================================
python run_desktop_webview.py
if %ERRORLEVEL% NEQ 0 (
    pause
)
