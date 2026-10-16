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

APP_VERSION = "1.7.6"
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
        # Menimpa berkas yang SEDANG DIBUKA pengguna (misal SintelisUtility.exe, SintelisUtility(1).exe, dsb)
        target_exe = exe_path
        standard_exe = os.path.join(exe_dir, "SintelisUtility.exe")
    else:
        target_exe = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist", "SintelisUtility.exe"))
        standard_exe = target_exe

    current_pid = os.getpid()

    ps1_file = os.path.join(tempfile.gettempdir(), "sintelis_updater.ps1")
    log_file = os.path.join(tempfile.gettempdir(), "sintelis_updater.log")

    target_esc = target_exe.replace("'", "''")
    standard_esc = standard_exe.replace("'", "''")
    temp_esc = temp_exe.replace("'", "''")
    log_esc = log_file.replace("'", "''")

    ps1_content = f"""# Sintelis Utility In-Place Auto-Updater (PowerShell)
$targetExe = '{target_esc}'
$standardExe = '{standard_esc}'
$tempExe = '{temp_esc}'
$logFile = '{log_esc}'
$callerPid = {current_pid}

function Log-Message([string]$msg) {{
    $timestamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    $line = "[$timestamp] $msg"
    try {{
        Add-Content -LiteralPath $logFile -Value $line -Encoding UTF8 -ErrorAction SilentlyContinue
    }} catch {{}}
}}

Log-Message "=============================================="
Log-Message "Updater Sintelis Utility Dimulai"
Log-Message "TARGET: $targetExe"
Log-Message "STANDARD: $standardExe"
Log-Message "TEMP_EXE: $tempExe"

# 1. Jeda 1.5 detik agar respon HTTP sukses terkirim ke antarmuka aplikasi
Start-Sleep -Milliseconds 1500

# 2. Hentikan paksa proses SintelisUtility dan proses pemanggil agar handle file terlepas
try {{
    Stop-Process -Id $callerPid -Force -ErrorAction SilentlyContinue
}} catch {{}}

try {{
    Get-Process -Name "SintelisUtility*" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
}} catch {{}}

try {{
    Get-Process | Where-Object {{ $_.ProcessName -like "*SintelisUtility*" -or ($_.Path -and $_.Path -like "*SintelisUtility*") }} | Stop-Process -Force -ErrorAction SilentlyContinue
}} catch {{}}

Start-Sleep -Milliseconds 1000

# 3. Sasaran utama penimpaan adalah berkas standar SintelisUtility.exe
$primaryTarget = $standardExe
if (-not $primaryTarget) {{
    $primaryTarget = $targetExe
}}

$copied = $false
for ($i = 1; $i -le 30; $i++) {{
    try {{
        Copy-Item -LiteralPath $tempExe -Destination $primaryTarget -Force -ErrorAction Stop
        $copied = $true
        Log-Message "Berkas utama berhasil ditimpa pada percobaan $i: $primaryTarget"
        break
    }} catch {{
        # Fallback swap rename ke .old jika file masih dilepaskan Windows
        try {{
            $oldExe = "$primaryTarget.old"
            if (Test-Path -LiteralPath $oldExe) {{ Remove-Item -LiteralPath $oldExe -Force -ErrorAction SilentlyContinue }}
            if (Test-Path -LiteralPath $primaryTarget) {{ Move-Item -LiteralPath $primaryTarget -Destination $oldExe -Force -ErrorAction Stop }}
            Copy-Item -LiteralPath $tempExe -Destination $primaryTarget -Force -ErrorAction Stop
            Remove-Item -LiteralPath $oldExe -Force -ErrorAction SilentlyContinue
            $copied = $true
            Log-Message "Berkas utama berhasil ditimpa via rename-swap pada percobaan $i: $primaryTarget"
            break
        }} catch {{
            Log-Message ("Percobaan $i gagal: $($_.Exception.Message)")
            Start-Sleep -Seconds 1
        }}
    }}
}}

if ($copied) {{
    $exeDir = Split-Path -Parent $primaryTarget

    # 4. Jika aplikasi sebelumnya dijalankan dari file duplikat (misal SintelisUtility (1).exe), hapus berkas duplikat tersebut
    if ($targetExe -and ($targetExe -ne $primaryTarget) -and (Test-Path -LiteralPath $targetExe)) {{
        try {{
            Remove-Item -LiteralPath $targetExe -Force -ErrorAction SilentlyContinue
            Log-Message "Menghapus berkas duplikat yang sebelumnya dibuka: $targetExe"
        }} catch {{}}
    }}

    # 5. Bersihkan semua sisa berkas duplikat browser (SintelisUtility (*).exe) di folder yang sama
    try {{
        Get-ChildItem -Path $exeDir -Filter "SintelisUtility (*).exe" -ErrorAction SilentlyContinue | ForEach-Object {{
            if ($_.FullName -ne $primaryTarget) {{
                Remove-Item -LiteralPath $_.FullName -Force -ErrorAction SilentlyContinue
                Log-Message "Membersihkan sisa berkas duplikat: $($_.FullName)"
            }}
        }}
    }} catch {{}}

    # 6. Hapus file sementara di Temp
    try {{
        Remove-Item -LiteralPath $tempExe -Force -ErrorAction SilentlyContinue
    }} catch {{}}

    # 7. Luncurkan HANYA berkas utama SintelisUtility.exe
    try {{
        Start-Process -FilePath $primaryTarget -WorkingDirectory $exeDir
        Log-Message "Aplikasi utama berhasil diluncurkan: $primaryTarget"
    }} catch {{
        Log-Message ("Gagal meluncurkan aplikasi utama: $($_.Exception.Message)")
    }}
}} else {{
    Log-Message "GAGAL menimpa berkas setelah 30 percobaan!"
}}

# Hapus skrip updater ini sendiri
try {{
    Remove-Item -LiteralPath $PSCommandPath -Force -ErrorAction SilentlyContinue
}} catch {{}}
"""

    with open(ps1_file, "w", encoding="utf-8") as f:
        f.write(ps1_content)

    # Jalankan PowerShell mandiri tanpa window (CREATE_NO_WINDOW = 0x08000000)
    cmd = [
        "powershell.exe",
        "-NoProfile",
        "-WindowStyle", "Hidden",
        "-ExecutionPolicy", "Bypass",
        "-File", ps1_file
    ]
    try:
        subprocess.Popen(
            cmd,
            creationflags=0x08000000,
            close_fds=True
        )
    except Exception:
        try:
            os.startfile(ps1_file)
        except Exception:
            subprocess.Popen(cmd)

    threading.Thread(target=lambda: (time.sleep(1.2), os._exit(0)), daemon=True).start()
    return {"ok": True, "message": "Restarting application to apply update..."}

