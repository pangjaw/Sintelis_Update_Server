"""
updater_engine.py — Cloudflare Auto-Updater Engine for Sintelis Utility
Checks version.json via Cloudflare domain, downloads new exe with progress tracking,
and performs atomic swap on Windows.
"""
import os
import sys
import time
import json
import urllib.request
import threading
import subprocess
import tempfile

APP_VERSION = "1.8.4"
DEFAULT_UPDATE_URL = "https://update.sintelboo.my.id/version.json"

_update_state = {
    "status": "idle",       # idle, checking, available, downloading, ready, error
    "server_version": None,
    "download_url": None,
    "changelog": [],
    "file_size": 0,
    "downloaded_bytes": 0,
    "percent": 0,
    "error": None,
    "target_temp_exe": None
}

_update_lock = threading.Lock()

def parse_semver(ver_str):
    try:
        clean = ver_str.lower().replace("v", "").strip()
        parts = [int(p) for p in clean.split(".")]
        while len(parts) < 3:
            parts.append(0)
        return tuple(parts[:3])
    except Exception:
        return (0, 0, 0)

def check_update(custom_url=None):
    url = custom_url or DEFAULT_UPDATE_URL
    with _update_lock:
        _update_state["status"] = "checking"
        _update_state["error"] = None

    last_err = None
    for attempt in range(2):
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "SintelisUtility-Client/1.5.1"}
            )
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            server_ver = data.get("version", "0.0.0")
            is_newer = parse_semver(server_ver) > parse_semver(APP_VERSION)

            with _update_lock:
                _update_state["server_version"] = server_ver
                _update_state["download_url"] = data.get("downloadUrl")
                _update_state["changelog"] = data.get("changelog", [])
                _update_state["file_size"] = data.get("fileSize", 0)
                if is_newer:
                    _update_state["status"] = "available"
                else:
                    _update_state["status"] = "idle"

            return {
                "updateAvailable": is_newer,
                "currentVersion": APP_VERSION,
                "serverVersion": server_ver,
                "changelog": data.get("changelog", []),
                "downloadUrl": data.get("downloadUrl"),
                "fileSize": data.get("fileSize", 0),
                "releaseDate": data.get("releaseDate", "")
            }
        except Exception as e:
            last_err = e
            time.sleep(0.5)

    with _update_lock:
        _update_state["status"] = "error"
        _update_state["error"] = str(last_err)
    return {
        "updateAvailable": False,
        "currentVersion": APP_VERSION,
        "error": str(last_err),
        "offline": True
    }

def _download_task(download_url):
    temp_dir = tempfile.gettempdir()
    temp_exe = os.path.join(temp_dir, "SintelisUtility_update.exe")

    with _update_lock:
        _update_state["status"] = "downloading"
        _update_state["downloaded_bytes"] = 0
        _update_state["percent"] = 0
        _update_state["target_temp_exe"] = temp_exe

    try:
        req = urllib.request.Request(
            download_url,
            headers={"User-Agent": "SintelisUtility-Client/1.5.0"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp, open(temp_exe, "wb") as out_f:
            total_len = int(resp.headers.get("Content-Length", 0)) or _update_state["file_size"] or 1
            downloaded = 0
            chunk_size = 1024 * 128

            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                out_f.write(chunk)
                downloaded += len(chunk)
                percent = min(100.0, round(downloaded / total_len * 100, 1))
                with _update_lock:
                    _update_state["downloaded_bytes"] = downloaded
                    _update_state["percent"] = percent

        with _update_lock:
            _update_state["status"] = "ready"
            _update_state["percent"] = 100.0
    except Exception as e:
        with _update_lock:
            _update_state["status"] = "error"
            _update_state["error"] = str(e)

def start_download(download_url=None):
    url = download_url or _update_state.get("download_url")
    if not url:
        return {"ok": False, "error": "Download URL tidak ditemukan"}
    t = threading.Thread(target=_download_task, args=(url,), daemon=True)
    t.start()
    return {"ok": True, "message": "Download started"}

def get_update_state():
    with _update_lock:
        return dict(_update_state)

def apply_update_and_restart():
    with _update_lock:
        temp_exe = _update_state.get("target_temp_exe")
        if not temp_exe or not os.path.isfile(temp_exe):
            return {"ok": False, "error": "File pembaruan belum siap diunduh"}

    if getattr(sys, "frozen", False):
        exe_path = os.path.abspath(sys.executable)
        exe_dir = os.path.dirname(exe_path)
        target_exe = exe_path
        standard_exe = os.path.join(exe_dir, "SintelisUtility.exe")
    else:
        target_exe = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist", "SintelisUtility.exe"))
        exe_dir = os.path.dirname(target_exe)
        standard_exe = target_exe

    current_pid = os.getpid()

    cmd_file = os.path.join(tempfile.gettempdir(), "sintelis_updater.cmd")
    log_file = os.path.join(tempfile.gettempdir(), "sintelis_updater.log")

    cmd_content = f"""@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
set "CALLER_PID={current_pid}"
set "TARGET_EXE={target_exe}"
set "STANDARD_EXE={standard_exe}"
set "TEMP_EXE={temp_exe}"
set "EXE_DIR={exe_dir}"
set "LOG_FILE={log_file}"

echo ============================================== >> "%LOG_FILE%"
echo [%date% %time%] In-Place Updater Dimulai >> "%LOG_FILE%"
echo [%date% %time%] CALLER_PID: %CALLER_PID% >> "%LOG_FILE%"
echo [%date% %time%] TARGET_EXE: %TARGET_EXE% >> "%LOG_FILE%"
echo [%date% %time%] STANDARD_EXE: %STANDARD_EXE% >> "%LOG_FILE%"
echo [%date% %time%] TEMP_EXE: %TEMP_EXE% >> "%LOG_FILE%"

:: 1. Jeda 1.5 detik agar respon HTTP sukses diterima oleh antarmuka aplikasi
timeout /t 2 /nobreak >nul

:: 2. Hentikan paksa proses pemanggil dan seluruh pohon prosesnya
echo [%date% %time%] Menghentikan proses pemanggil (PID: %CALLER_PID%)... >> "%LOG_FILE%"
taskkill /F /PID %CALLER_PID% /T >nul 2>&1
taskkill /F /IM "SintelisUtility*.exe" /T >nul 2>&1
timeout /t 2 /nobreak >nul

:: 3. Timpa file dengan perulangan hingga 30 kali
set "SUCCESS=0"
for /L %%i in (1,1,30) do (
    if "!SUCCESS!"=="0" (
        echo [%date% %time%] Mencoba menimpa TARGET_EXE (Percobaan %%i/30)... >> "%LOG_FILE%"
        copy /Y "%TEMP_EXE%" "%TARGET_EXE%" >nul 2>&1
        if not errorlevel 1 (
            set "SUCCESS=1"
            echo [%date% %time%] TARGET_EXE berhasil ditimpa pada percobaan %%i! >> "%LOG_FILE%"
        ) else (
            :: Coba teknik rename swap jika file masih dikunci
            if exist "%TARGET_EXE%.old" del /F /Q "%TARGET_EXE%.old" >nul 2>&1
            move /Y "%TARGET_EXE%" "%TARGET_EXE%.old" >nul 2>&1
            copy /Y "%TEMP_EXE%" "%TARGET_EXE%" >nul 2>&1
            if not errorlevel 1 (
                set "SUCCESS=1"
                del /F /Q "%TARGET_EXE%.old" >nul 2>&1
                echo [%date% %time%] TARGET_EXE berhasil ditimpa via rename-swap pada percobaan %%i! >> "%LOG_FILE%"
            ) else (
                timeout /t 1 /nobreak >nul
            )
        )
    )
)

:: 4. Jika TARGET_EXE berbeda dengan STANDARD_EXE, sinkronkan juga STANDARD_EXE
if not "%TARGET_EXE%"=="%STANDARD_EXE%" (
    echo [%date% %time%] Menyinkronkan STANDARD_EXE: %STANDARD_EXE% >> "%LOG_FILE%"
    copy /Y "%TEMP_EXE%" "%STANDARD_EXE%" >nul 2>&1
)

:: 5. Jalankan aplikasi terbaru jika penimpaan berhasil
if "!SUCCESS!"=="1" (
    echo [%date% %time%] Berhasil! Menghapus biner sementara di Temp... >> "%LOG_FILE%"
    del /F /Q "%TEMP_EXE%" >nul 2>&1
    echo [%date% %time%] Meluncurkan aplikasi versi terbaru: %TARGET_EXE% >> "%LOG_FILE%"
    start "" /D "%EXE_DIR%" "%TARGET_EXE%"
) else (
    echo [%date% %time%] GAGAL menimpa berkas setelah 30 percobaan! >> "%LOG_FILE%"
)

:: 6. Selesai dan bersihkan skrip updater ini
(goto) 2>nul & del "%~f0"
"""

    with open(cmd_file, "w", encoding="utf-8") as f:
        f.write(cmd_content)

    # DETACHED_PROCESS (0x00000008) + CREATE_NEW_PROCESS_GROUP (0x00000200) + CREATE_NO_WINDOW (0x08000000)
    flags = 0x00000008 | 0x00000200 | 0x08000000
    try:
        subprocess.Popen(
            ["cmd.exe", "/c", cmd_file],
            creationflags=flags,
            close_fds=True
        )
    except Exception:
        try:
            os.startfile(cmd_file)
        except Exception:
            subprocess.Popen(["cmd.exe", "/c", cmd_file])

    threading.Thread(target=lambda: (time.sleep(1.2), os._exit(0)), daemon=True).start()
    return {"ok": True, "message": "Restarting application to apply update..."}


