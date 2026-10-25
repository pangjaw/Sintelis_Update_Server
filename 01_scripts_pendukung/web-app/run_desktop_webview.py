"""
Sintelis Utility — Desktop WebView App
Menjalankan web-app hasil build Vite dalam native window.
API folder dialog & save file via HTTP endpoint (tidak pakai pywebview js_api).
"""
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)
import base64
import http.server
import io
import json
import os
import time
from datetime import datetime
from pathlib import Path
import re
import socketserver
import sys
import tempfile
import threading
import urllib.parse
import shutil
import subprocess

import webview
from pdf2image import convert_from_path
from PIL import ImageOps, Image
import pytesseract
import updater_engine
from timemark_engine import date_changer_engine, personnel_changer_engine, pipeline_runner

if getattr(sys, 'frozen', False):
    BUNDLE_DIR = sys._MEIPASS
else:
    BUNDLE_DIR = os.path.dirname(os.path.abspath(__file__))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(BUNDLE_DIR, "dist")
PORT = 18725

ENGINE_DIR = os.path.join(BUNDLE_DIR, "timemark_engine")
if not os.path.isdir(ENGINE_DIR):
    ENGINE_DIR = os.path.join(BASE_DIR, "timemark_engine")

def make_script_cmd(script_name, script_args):
    is_frozen = getattr(sys, 'frozen', False)
    if is_frozen:
        return [sys.executable, "--run-script", os.path.basename(script_name)] + script_args
    else:
        script_path = os.path.join(ENGINE_DIR, os.path.basename(script_name))
        return [sys.executable, script_path] + script_args

def get_tesseract_cmd():
    candidates = [
        os.path.join(BUNDLE_DIR, "tesseract", "tesseract.exe"),
        os.path.join(BUNDLE_DIR, "Tesseract-OCR", "tesseract.exe"),
        os.path.join(BASE_DIR, "tesseract", "tesseract.exe"),
        os.path.join(BASE_DIR, "Tesseract-OCR", "tesseract.exe"),
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    import shutil
    which = shutil.which("tesseract")
    if which:
        return which
    return r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def get_poppler_dir():
    candidates = [
        os.path.join(BUNDLE_DIR, "poppler"),
        os.path.join(BUNDLE_DIR, "Aplikasi", "poppler"),
        os.path.join(BASE_DIR, "poppler"),
        os.path.join(BASE_DIR, "..", "Aplikasi", "poppler"),
    ]
    for c in candidates:
        if os.path.isdir(c):
            return c
    return os.path.join(BASE_DIR, "..", "Aplikasi", "poppler")

TESSERACT_CMD = get_tesseract_cmd()
POPPLER_DIR = get_poppler_dir()

# Set TESSDATA_PREFIX otomatis jika ada tessdata
_tessdata_candidate = os.path.join(os.path.dirname(TESSERACT_CMD), "tessdata")
if os.path.isdir(_tessdata_candidate):
    os.environ["TESSDATA_PREFIX"] = _tessdata_candidate
if os.path.isfile(TESSERACT_CMD):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

# ---- Logging ke file ----
LOG_FILE = os.path.join(tempfile.gettempdir(), "sintelis_utility.log")

def _log(msg):
    """Append log entry ke file log dengan timestamp."""
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as lf:
            lf.write(f"[{ts}] {msg}\n")
            lf.flush()
    except Exception:
        pass  # silent fail — jangan ganggu app utama

# Fix blank screen setelah minimize lama — disable GPU acceleration WebView2
# CalculateNativeWinOcclusion: cegah Windows suspend rendering pipeline saat window minimized
# Optimasi Memori: Batasi heap JS V8 ke 384MB, batasi cache, dan paksa agresif garbage collection
os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = (
    "--disable-gpu "
    "--disable-features=CalculateNativeWinOcclusion "
    "--renderer-process-limit=1 "
    "--js-flags=--max-old-space-size=384 "
    "--disk-cache-size=10485760 "
    "--media-cache-size=10485760 "
    "--disable-dev-shm-usage "
    "--aggressive-cache-discard"
)

APP_DATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "SintelisUtility")
os.makedirs(APP_DATA_DIR, exist_ok=True)
ACCOUNTS_FILE = os.path.join(APP_DATA_DIR, "p3ste_accounts.json")


def _init_persistent_storage():
    """
    Memastikan direktori APP_DATA_DIR (%LOCALAPPDATA%\\SintelisUtility)
    memiliki data awal employee_presets.json dan daftar_pegawai.json.
    Jika belum ada (instalasi baru atau update pertama kali),
    salin template dari ENGINE_DIR atau BASE_DIR/config.
    JANGAN TIMPA jika berkas sudah ada di APP_DATA_DIR.
    """
    try:
        os.makedirs(APP_DATA_DIR, exist_ok=True)
        user_presets = os.path.join(APP_DATA_DIR, "employee_presets.json")
        if not os.path.isfile(user_presets) or os.path.getsize(user_presets) < 10:
            for candidate in [
                os.path.join(ENGINE_DIR, "employee_presets.json"),
                os.path.join(BASE_DIR, "config", "employee_presets.json"),
            ]:
                if os.path.isfile(candidate) and os.path.getsize(candidate) > 10:
                    shutil.copy2(candidate, user_presets)
                    _log(f"Initialized persistent employee_presets.json from: {candidate}")
                    break

        user_pegawai = os.path.join(APP_DATA_DIR, "daftar_pegawai.json")
        if not os.path.isfile(user_pegawai) or os.path.getsize(user_pegawai) < 10:
            for candidate in [
                os.path.join(ENGINE_DIR, "daftar_pegawai.json"),
                os.path.join(BASE_DIR, "config", "daftar_pegawai.json"),
            ]:
                if os.path.isfile(candidate) and os.path.getsize(candidate) > 10:
                    shutil.copy2(candidate, user_pegawai)
                    _log(f"Initialized persistent daftar_pegawai.json from: {candidate}")
                    break
    except Exception as e:
        _log(f"Persistent storage init notice: {e}")


_init_persistent_storage()


def _atomic_write_json(file_path, data):
    """Menulis data JSON secara atomik menggunakan berkas temporer untuk mencegah korupsi data."""
    try:
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        tmp_path = f"{file_path}.tmp.{os.getpid()}"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, file_path)
        return True
    except Exception as e:
        _log(f"Atomic write error for {file_path}: {e}")
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False


_selected_folder = None
_was_minimized = False


def on_minimized():
    """Track bahwa window pernah di-minimize (untuk trigger recovery di restored)."""
    global _was_minimized
    _was_minimized = True
    _log("🟡 EVENT: minimized")


_was_minimized = False

# ---- P3-STE Downloader Engine State ----
_p3ste_state = {
    "running": False,
    "cancelled": False,
    "current": 0,
    "total": 0,
    "logs": [],
    "downloaded_files": [],
    "error": None
}

def _add_p3ste_log(log_type, msg):
    ts = time.strftime("%H:%M:%S")
    _p3ste_state["logs"].append({"type": log_type, "msg": msg, "ts": ts})
    _log(f"P3STE [{log_type.upper()}] {msg}")
_current_playwright_context = None

def _cleanup_p3ste_browser_profile(user_data_dir=None):
    """Bersihkan proses msedge/chrome yatim (orphaned) yang mengunci p3ste_browser_profile serta hapus lockfile."""
    if not user_data_dir:
        user_data_dir = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "SintelisUtility", "p3ste_browser_profile")
    try:
        import psutil
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                pname = (proc.info.get("name") or "").lower()
                if pname in ("msedge.exe", "chrome.exe"):
                    cmdline = " ".join(proc.info.get("cmdline") or [])
                    if "p3ste_browser_profile" in cmdline:
                        proc.kill()
            except Exception:
                pass
    except Exception:
        try:
            subprocess.run(
                [
                    "powershell.exe", "-NoProfile", "-Command",
                    "Get-CimInstance Win32_Process -Filter \"Name = 'msedge.exe' OR Name = 'chrome.exe'\" | Where-Object { $_.CommandLine -like '*p3ste_browser_profile*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
                ],
                capture_output=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000),
                timeout=8
            )
        except Exception:
            pass

    for lock_name in ("lockfile", "SingletonLock", "SingletonCookie", "SingletonSocket"):
        lock_path = os.path.join(user_data_dir, lock_name)
        if os.path.exists(lock_path):
            try:
                os.remove(lock_path)
            except Exception:
                pass


def _cancel_all_processes():
    global _current_playwright_context, _p3ste_state
    _p3ste_state["cancelled"] = True
    _p3ste_state["running"] = False
    _add_p3ste_log("warn", "🛑 Menghentikan semua proses yang sedang berjalan...")
    if _current_playwright_context:
        try:
            _current_playwright_context.close()
            _add_p3ste_log("info", "✓ Browser engine berhasil ditutup.")
        except Exception as e:
            _log(f"Notice closing browser context: {e}")
        _current_playwright_context = None
    _cleanup_p3ste_browser_profile()

def _get_unique_p3ste_filename(target_folder, filename, existing_names=None):
    """
    Menghasilkan nama file unik dengan menambahkan (2), (3), dst. jika nama file sudah ada
    di target_folder atau sudah digunakan dalam sesi pengunduhan saat ini.
    Contoh:
    checklist.pdf -> checklist.pdf (jika belum ada)
    checklist.pdf -> checklist (2).pdf (jika sudah ada)
    checklist.pdf -> checklist (3).pdf (jika checklist (2).pdf sudah ada)
    """
    clean_fn = re.sub(r'[<>:"/\\|?*]', '_', filename).strip()
    base, ext = os.path.splitext(clean_fn)
    if not ext:
        ext = ".pdf"

    m = re.search(r'^(.*?)\s*\((\d+)\)$', base)
    if m:
        base_clean = m.group(1).strip()
        counter = int(m.group(2))
    else:
        base_clean = base
        counter = 1

    candidate_fn = f"{base}{ext}"
    candidate_path = os.path.join(target_folder, candidate_fn)

    while os.path.exists(candidate_path) or (existing_names and candidate_fn in existing_names):
        counter += 1
        candidate_fn = f"{base_clean} ({counter}){ext}"
        candidate_path = os.path.join(target_folder, candidate_fn)

    return candidate_fn, candidate_path

def _correct_filename_date(filename, table_date):
    """
    Jika tanggal di nama file dari server berbeda dengan tanggal resmi di kolom tabel web P3-STE,
    ganti prefix tanggal nama file dengan tanggal dari tabel web.
    Contoh: '02-08-2026_PERAWATAN...pdf' -> '02-07-2026_PERAWATAN...pdf'
    """
    if not table_date or not re.match(r'^\d{2}-\d{2}-\d{4}$', table_date):
        return filename, None
    
    # Cek apakah nama file diawali format DD-MM-YYYY
    m = re.match(r'^(\d{2}-\d{2}-\d{4})(_.*\.pdf)$', filename, re.IGNORECASE)
    if m:
        server_date = m.group(1)
        suffix = m.group(2)
        if server_date != table_date:
            corrected_fn = f"{table_date}{suffix}"
            return corrected_fn, server_date
    elif filename.lower().startswith("checklist_"):
        # Jika server tidak mengembalikan tanggal sama sekali
        return f"{table_date}_{filename}", None
        
    return filename, None

def _parse_curl_header_cookies(curl_cmd):
    """Parse headers and cookies from cURL string (mendukung bash, cmd, powershell, case-insensitive)."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    }
    cookies = {}
    
    if not curl_cmd:
        return headers, cookies

    # Clean CMD carets and newlines
    clean_cmd = curl_cmd.replace("^\r\n", " ").replace("^\n", " ").replace("^\"", "\"").replace("^", "")
    
    # 1. Extract headers (-H '...' or --header '...' or -H "...")
    header_matches = re.findall(r'(?:-H|--header)\s+[\'"]([^\'"]+)[\'"]', clean_cmd, re.IGNORECASE)
    for h in header_matches:
        if ":" in h:
            k, v = h.split(":", 1)
            headers[k.strip()] = v.strip()
            
    # 2. Case-insensitive search for Cookie header
    cookie_str = ""
    for k, v in list(headers.items()):
        if k.lower() == "cookie":
            cookie_str = v
            break
            
    # 3. Extract -b '...' or --cookie '...'
    cookie_flag_matches = re.findall(r'(?:-b|--cookie)\s+[\'"]([^\'"]+)[\'"]', clean_cmd, re.IGNORECASE)
    if cookie_flag_matches:
        cookie_str += ("; " if cookie_str else "") + cookie_flag_matches[0]
        
    if cookie_str:
        for c in cookie_str.split(";"):
            if "=" in c:
                ck, cv = c.strip().split("=", 1)
                ck = ck.strip()
                cv = cv.strip()
                if ck:
                    cookies[ck] = cv
                    
    return headers, cookies

def _safe_evaluate(page, js_func, arg=None, max_retries=6, delay=1.5):
    """Jalankan page.evaluate dengan retry otomatis jika context hancur saat navigasi."""
    last_err = None
    for attempt in range(max_retries):
        try:
            if arg is not None:
                return page.evaluate(js_func, arg)
            return page.evaluate(js_func)
        except Exception as e:
            last_err = e
            err_msg = str(e)
            if "destroyed" in err_msg or "navigating" in err_msg or "Target closed" not in err_msg:
                time.sleep(delay)
                continue
            raise e
    _log(f"safe_evaluate notice (retried {max_retries}x): {last_err}")
    return None

def _run_p3ste_download_task(nipp, password, awal, akhir, type_val, target_folder, start_id=None, end_id=None, show_browser=False, curl_cmd=""):
    global _p3ste_state
    _p3ste_state["running"] = True
    _p3ste_state["cancelled"] = False
    _p3ste_state["current"] = 0
    _p3ste_state["total"] = 0
    _p3ste_state["logs"] = []
    _p3ste_state["downloaded_files"] = []
    _p3ste_state["error"] = None

    try:
        headers, cookies = {}, {}
        if curl_cmd:
            _add_p3ste_log("info", "Memparsing Header & Cookie dari string cURL...")
            headers, cookies = _parse_curl_header_cookies(curl_cmd)
        else:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
                "Referer": "https://p3-ste.kai.id/"
            }
        
        import requests
        requests.packages.urllib3.disable_warnings()
        
        session = requests.Session()
        session.verify = False
        session.headers.update(headers)
        session.cookies.update(cookies)

        type_name = "pemeriksaan" if str(type_val) == "1" else "perawatan"

        # Check for Direct ID Range Download Mode
        if start_id and end_id:
            try:
                s_id = int(str(start_id).strip())
                e_id = int(str(end_id).strip())
                if s_id > 0 and e_id >= s_id:
                    total_ids = e_id - s_id + 1
                    _add_p3ste_log("info", f"Mode Unduh Langsung ID: {s_id} s.d. {e_id} (Total {total_ids} target)...")
                    _p3ste_state["total"] = total_ids
                    os.makedirs(target_folder, exist_ok=True)
                    session_filenames = set()
                    
                    for current_id in range(s_id, e_id + 1):
                        if _p3ste_state["cancelled"]:
                            _add_p3ste_log("warn", "Pengunduhan dibatalkan pengguna.")
                            break
                            
                        total_downloaded = len(_p3ste_state["downloaded_files"]) + 1
                        _p3ste_state["current"] = total_downloaded
                        pdf_url = f"https://p3-ste.kai.id/cetak_checklist/report/{type_name}/exports/pdf/{current_id}?false"
                        fn = f"checklist_{current_id}.pdf"
                        
                        _add_p3ste_log("info", f"[{current_id}] Mencoba unduh checklist ID {current_id}...")
                        
                        download_success = False
                        last_err = ""
                        max_attempts = 3
                        for attempt in range(max_attempts):
                            if _p3ste_state["cancelled"]: break
                            try:
                                fresp = session.get(pdf_url, timeout=30)
                                if fresp.status_code == 200 and fresp.content[:4] == b"%PDF":
                                    cd = fresp.headers.get("Content-Disposition", "")
                                    if "filename=" in cd:
                                        cd_fn = re.search(r'filename=["\']?([^"\';]+)["\']?', cd)
                                        if cd_fn:
                                            fn = cd_fn.group(1).strip().strip('"').strip("'")

                                    fn, out_path = _get_unique_p3ste_filename(target_folder, fn, session_filenames)

                                    with open(out_path, "wb") as pf:
                                        pf.write(fresp.content)

                                    file_size = len(fresp.content)
                                    session_filenames.add(fn)
                                    _p3ste_state["downloaded_files"].append({
                                        "name": fn,
                                        "path": out_path,
                                        "size": file_size
                                    })
                                    retry_tag = f" (coba ulang ke-{attempt})" if attempt > 0 else ""
                                    _add_p3ste_log("success", f"✓ Tersimpan: {fn} ({file_size // 1024} KB){retry_tag}")
                                    download_success = True
                                    break
                                elif fresp.status_code in (500, 502, 503, 504, 429):
                                    last_err = f"HTTP {fresp.status_code}"
                                    if attempt < max_attempts - 1:
                                        time.sleep(1.5 * (attempt + 1))
                                        continue
                                else:
                                    last_err = f"HTTP {fresp.status_code}"
                                    break
                            except Exception as fe:
                                last_err = str(fe)
                                if attempt < max_attempts - 1:
                                    time.sleep(1.5 * (attempt + 1))
                                    continue

                        if not download_success and not _p3ste_state["cancelled"]:
                            _add_p3ste_log("error", f"✗ ID {current_id} Gagal: {last_err}")

                        time.sleep(0.15)

                    _add_p3ste_log("success", f"Selesai! Berhasil mengunduh total {len(_p3ste_state['downloaded_files'])} file PDF.")
                    return
            except Exception as id_err:
                _add_p3ste_log("warn", f"Pengecekan ID Range: {id_err}. Melanjutkan ke mode Scraper Halaman...")

        mode_desc = "Visual / Jendela Tampil" if show_browser else "Headless"
        _add_p3ste_log("info", f"Memulai Browser Engine ({type_name.upper()} - {mode_desc})...")

        if "PLAYWRIGHT_BROWSERS_PATH" not in os.environ:
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.expandvars(r"%LOCALAPPDATA%\ms-playwright")

        user_data_dir = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "SintelisUtility", "p3ste_browser_profile")
        os.makedirs(user_data_dir, exist_ok=True)
        _cleanup_p3ste_browser_profile(user_data_dir)

        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            context = None
            last_err = None
            primary_err = None
            for ch in ["msedge", "msedge", "chrome", None]:
                try:
                    ch_label = f"Channel: {ch}" if ch else "Default Chromium"
                    context = p.chromium.launch_persistent_context(
                        user_data_dir=user_data_dir,
                        channel=ch,
                        headless=not show_browser,
                        viewport=None,
                        user_agent=headers.get("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
                        args=[
                            "--disable-blink-features=AutomationControlled",
                            "--no-sandbox",
                            "--disable-infobars"
                        ],
                        ignore_default_args=["--enable-automation"]
                    )
                    _add_p3ste_log("info", f"✓ Browser engine aktif ({ch_label}, Profile: Persistent).")
                    global _current_playwright_context
                    _current_playwright_context = context
                    break
                except Exception as b_err:
                    if ch in ("msedge", "chrome") and primary_err is None:
                        primary_err = b_err
                    last_err = primary_err or b_err
                    _cleanup_p3ste_browser_profile(user_data_dir)
                    time.sleep(0.8)
                    continue

            if not context:
                raise Exception(
                    f"Gagal menjalankan browser engine: {last_err}. "
                    "Pastikan Microsoft Edge atau Google Chrome terpasang di Windows."
                )

            # Injeksi cookie dari cURL jika ada
            if cookies:
                pw_cookies = []
                for ck, cv in cookies.items():
                    pw_cookies.append({
                        "name": ck,
                        "value": cv,
                        "url": "https://p3-ste.kai.id"
                    })
                try:
                    context.add_cookies(pw_cookies)
                except Exception as ce:
                    pass

            page = context.pages[0] if len(context.pages) > 0 else context.new_page()

            # 1. Buka halaman rekap_checklist dengan query filter langsung
            query_url = f"https://p3-ste.kai.id/rekap_checklist?awal={awal.replace('/', '%2F')}&akhir={akhir.replace('/', '%2F')}&type={type_val}&asset=0&category=0&daop=1&resort=170&nipp=0&noasset=0&hasil=baik&status=done"
            _add_p3ste_log("info", f"Membuka portal P3-STE ({type_name.upper()})...")
            
            page.goto(query_url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(2500)

            cur_url = page.url
            page_title = page.title()
            _add_p3ste_log("info", f"Halaman termuat: '{page_title}'")

            # Cek apakah berada di halaman Login
            is_login_page = _safe_evaluate(page, """() => {
                const hasLoginForm = document.querySelector('input#nipp, input[name="nipp"], input#kata_sandi, input[name="kata_sandi"], form[action*="auth"]');
                const hasDashboard = document.querySelector('#submited, #table, a[href*="logout"], a[href*="rekap_checklist"], .navbar-nav, .sidebar');
                if (hasDashboard) return false;
                return !!hasLoginForm || window.location.pathname === '/' || document.title.toLowerCase().includes('login');
            }""")

            if is_login_page:
                if not nipp or not password:
                    _add_p3ste_log("error", "⚠️ Sesi login habis dan data NIPP / Kata Sandi belum diatur.")
                    raise Exception("Sesi login kedaluwarsa. Silakan lengkapi NIPP dan Kata Sandi pada menu pengaturan akun.")

                _add_p3ste_log("info", f"🔐 Sesi belum aktif. Melakukan login otomatis untuk NIPP: {nipp}...")
                
                # Pastikan berada di URL login jika sempat terlempar
                if "rekap_checklist" not in page.url and "/auth" not in page.url and page.url.rstrip("/") != "https://p3-ste.kai.id":
                    page.goto("https://p3-ste.kai.id/", wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_timeout(1500)

                # Isi formulir login dan selesaikan captcha matematika secara otomatis
                fill_res = _safe_evaluate(page, f"""() => {{
                    const nippInp = document.querySelector('input#nipp, input[name="nipp"]');
                    const passInp = document.querySelector('input#kata_sandi, input[name="kata_sandi"]');
                    const cptInp = document.querySelector('input#captcha, input[name="captcha"]');
                    const cptRes = document.querySelector('input#cptres, input[name="cptres"]');
                    const spanMath = document.querySelector('span[style*="font-size"]');

                    if (!nippInp || !passInp || !cptInp) {{
                        return {{ ok: false, error: 'Elemen input form login tidak ditemukan di halaman website P3-STE.' }};
                    }}

                    nippInp.value = {json.dumps(nipp)};
                    nippInp.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    nippInp.dispatchEvent(new Event('change', {{ bubbles: true }}));

                    passInp.value = {json.dumps(password)};
                    passInp.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    passInp.dispatchEvent(new Event('change', {{ bubbles: true }}));

                    let captchaVal = "";
                    if (cptRes && cptRes.value) {{
                        captchaVal = cptRes.value.trim();
                    }} else if (spanMath) {{
                        try {{
                            const expr = spanMath.innerText.trim();
                            const parts = expr.split('+');
                            if (parts.length === 2) {{
                                captchaVal = String(parseInt(parts[0].trim()) + parseInt(parts[1].trim()));
                            }}
                        }} catch (e) {{}}
                    }}

                    cptInp.value = captchaVal;
                    cptInp.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    cptInp.dispatchEvent(new Event('change', {{ bubbles: true }}));

                    return {{ ok: true, captcha: captchaVal }};
                }}""")

                if not fill_res or not fill_res.get("ok"):
                    err = fill_res.get("error") if fill_res else "Gagal mengisi input formulir login"
                    raise Exception(err)

                _add_p3ste_log("info", f"Form terisi (Captcha: {fill_res.get('captcha', '-')}). Mengirim autentikasi...")
                
                # Klik tombol submit Masuk
                try:
                    page.click('button[type="submit"], #form-login button')
                except Exception:
                    _safe_evaluate(page, "() => { document.querySelector('form#form-login')?.submit(); }")
                
                page.wait_for_timeout(3000)

                # Periksa apakah berhasil login atau muncul alert pesan error dari web
                login_check = _safe_evaluate(page, """() => {
                    const alertEl = document.querySelector('.alert-danger, .alert, .invalid-feedback, .text-danger, .error-message, .swal2-html-container');
                    let errText = alertEl ? alertEl.innerText.trim() : "";
                    const hasDashboard = document.querySelector('#submited, #table, a[href*="logout"], a[href*="rekap_checklist"], .navbar-nav, .sidebar');
                    const isLogged = !!hasDashboard || (!window.location.pathname.includes('auth') && window.location.pathname !== '/' && !document.title.toLowerCase().includes('login'));
                    return {
                        isLogged: isLogged,
                        errText: errText
                    };
                }""")

                if login_check and not login_check.get("isLogged"):
                    page.wait_for_timeout(2000)
                    login_check2 = _safe_evaluate(page, """() => {
                        const alertEl = document.querySelector('.alert-danger, .alert, .invalid-feedback, .text-danger, .error-message, .swal2-html-container');
                        let errText = alertEl ? alertEl.innerText.trim() : "";
                        const hasDashboard = document.querySelector('#submited, #table, a[href*="logout"], a[href*="rekap_checklist"], .navbar-nav, .sidebar');
                        return {
                            isLogged: !!hasDashboard,
                            errText: errText
                        };
                    }""")
                    if login_check2:
                        if login_check2.get("isLogged"):
                            login_check["isLogged"] = True
                        elif login_check2.get("errText"):
                            login_check["errText"] = login_check2.get("errText")

                if not login_check.get("isLogged"):
                    err_msg = login_check.get("errText")
                    if err_msg:
                        _add_p3ste_log("error", f"❌ Gagal Login dari Website P3-STE: {err_msg}")
                        raise Exception(f"P3-STE Menolak Login: {err_msg}")
                    else:
                        _add_p3ste_log("error", "❌ Gagal Login P3-STE: NIPP atau Kata Sandi salah / Sesi ditolak.")
                        raise Exception("Gagal Login P3-STE: NIPP atau Kata Sandi salah / Sesi ditolak.")

                _add_p3ste_log("success", f"✓ Login Berhasil untuk NIPP: {nipp}! Membuka halaman rekap...")
                page.goto(query_url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(2500)
            else:
                _add_p3ste_log("success", "✓ Sesi login profil browser masih aktif. Melanjutkan pengunduhan...")

            # Sinkronisasi cookie terbaru dari browser ke Requests session
            try:
                live_cookies = context.cookies(["https://p3-ste.kai.id"])
                for lc in live_cookies:
                    session.cookies.set(lc["name"], lc["value"], domain="p3-ste.kai.id")
            except Exception as se_err:
                _add_p3ste_log("warn", f"Sinkronisasi cookie session notice: {se_err}")

            # 1. Terapkan nilai filter pada form dan klik tombol filter
            _add_p3ste_log("info", "Memasukkan filter tanggal & jenis laporan...")
            _safe_evaluate(page, """(args) => {
                const { awal, akhir, typeVal } = args;
                const awalInp = document.querySelector('input[name="awal"], #awal, input[placeholder*="Awal"]');
                if (awalInp) {
                    awalInp.value = awal;
                    awalInp.dispatchEvent(new Event('input', { bubbles: true }));
                    awalInp.dispatchEvent(new Event('change', { bubbles: true }));
                }
                
                const akhirInp = document.querySelector('input[name="akhir"], #akhir, input[placeholder*="Akhir"]');
                if (akhirInp) {
                    akhirInp.value = akhir;
                    akhirInp.dispatchEvent(new Event('input', { bubbles: true }));
                    akhirInp.dispatchEvent(new Event('change', { bubbles: true }));
                }
                
                const typeSel = document.querySelector('select[name="type"], #type');
                if (typeSel) {
                    typeSel.value = typeVal;
                    typeSel.dispatchEvent(new Event('change', { bubbles: true }));
                }
            }""", {"awal": awal, "akhir": akhir, "typeVal": type_val})

            clicked_filter = _safe_evaluate(page, """() => {
                const btn = document.querySelector('#submited, button[type="submit"], input[type="submit"], button.btn-primary');
                if (btn) {
                    btn.click();
                    return true;
                }
                return false;
            }""")
            if clicked_filter:
                _add_p3ste_log("info", "Tombol Filter diklik. Menunggu 10 data awal & tombol Cetak muncul di layar...")
            else:
                _add_p3ste_log("info", "Menunggu data tabel awal termuat...")

            # 2. Tunggu 10 data awal & tombol Cetak muncul di layar (seperti Gambar 3)
            initial_ready = False
            for _ in range(90):
                if _p3ste_state["cancelled"]: break
                page.wait_for_timeout(1000)
                row_status = _safe_evaluate(page, """() => {
                    // Cek kemunculan tombol Cetak pada tabel
                    const cetakBtns = Array.from(document.querySelectorAll('table tbody tr a, table tbody tr button, table tbody tr .btn-danger'))
                        .filter(b => b.innerText.trim().toLowerCase().includes('cetak') || (b.getAttribute('href') || '').includes('pdf') || (b.getAttribute('onclick') || '').includes('cetak'));
                    const trs = document.querySelectorAll('table tbody tr');
                    const empty = document.querySelector('.dataTables_empty');
                    const emptyText = empty ? empty.innerText.trim() : '';
                    if (empty && (emptyText.includes('Loading') || emptyText.includes('memuat') || emptyText.includes('...'))) {
                        return { ready: false, count: 0 };
                    }
                    if (cetakBtns.length > 0) {
                        return { ready: true, count: cetakBtns.length };
                    }
                    if (trs.length > 0 && !empty) {
                        return { ready: true, count: trs.length };
                    }
                    return { ready: false, count: 0 };
                }""") or {}
                
                if row_status.get("ready"):
                    _add_p3ste_log("success", f"✓ {row_status.get('count')} data awal & tombol Cetak berhasil tampil di layar.")
                    initial_ready = True
                    break

            if not initial_ready:
                _add_p3ste_log("warn", "Data awal belum terdeteksi. Mencoba melanjutkan...")

            page.wait_for_timeout(2000)

            # Sinkronisasi cookie live dari browser ke Requests session sebelum unduhan
            try:
                live_cookies = context.cookies(["https://p3-ste.kai.id"])
                for lc in live_cookies:
                    session.cookies.set(lc["name"], lc["value"], domain="p3-ste.kai.id")
                _add_p3ste_log("info", f"✓ Sesi browser terverifikasi ({len(live_cookies)} cookies).")
            except Exception as se_err:
                _add_p3ste_log("warn", f"Notice sinkronisasi cookie: {se_err}")

            # Diagnostik status tabel & Deteksi Total Data Target
            page_diag = _safe_evaluate(page, r"""() => {
                let total = 0;
                try {
                    if (typeof $ !== 'undefined' && $.fn && $.fn.DataTable) {
                        const tbls = Array.from(document.querySelectorAll('table'));
                        for (const t of tbls) {
                            if ($.fn.DataTable.isDataTable(t)) {
                                const info = $(t).DataTable().page.info();
                                if (info && info.recordsDisplay > 0) total = info.recordsDisplay;
                                else if (info && info.recordsTotal > 0) total = info.recordsTotal;
                                if (total > 0) break;
                            }
                        }
                    }
                } catch (e) {}

                const infoEl = document.querySelector('.dataTables_info, #table_info, [id*="_info"]');
                const infoText = infoEl ? infoEl.innerText : null;
                if (!total && infoText) {
                    const m = infoText.match(/(?:dari|of)\s+([\d.,]+)/i);
                    if (m) {
                        total = parseInt(m[1].replace(/[.,]/g, ''), 10) || 0;
                    }
                }

                const rows = document.querySelectorAll('#table tbody tr, table tbody tr');
                const emptyEl = document.querySelector('.dataTables_empty');
                return {
                    info: infoText,
                    total: total,
                    rowCount: (!emptyEl && rows.length > 0) ? rows.length : 0
                };
            }""") or {}
            
            if page_diag.get("info"):
                _add_p3ste_log("info", f"Status Tabel: {page_diag['info']}")

            detected_total = page_diag.get("total", 0)
            if detected_total > 0:
                _p3ste_state["total"] = detected_total
                _add_p3ste_log("info", f"📊 Terdeteksi target total: {detected_total} file checklist.")

            os.makedirs(target_folder, exist_ok=True)
            checkpoint_file = os.path.join(target_folder, ".p3ste_checkpoint.json")
            checkpoint_data = {}
            if os.path.isfile(checkpoint_file):
                try:
                    with open(checkpoint_file, "r", encoding="utf-8") as cf:
                        checkpoint_data = json.load(cf)
                except Exception:
                    checkpoint_data = {}

            if checkpoint_data:
                _add_p3ste_log("info", f"📌 Ditemukan checkpoint {len(checkpoint_data)} file. Fitur Resume otomatis aktif.")

            page_index = 1
            total_downloaded = 0
            downloaded_ids = set()
            session_filenames = set()
            failed_queue = []

            while True:
                if _p3ste_state["cancelled"]:
                    _add_p3ste_log("warn", "Pengunduhan dibatalkan pengguna.")
                    break

                _add_p3ste_log("info", f"--- Memproses Halaman {page_index} ---")
                
                # Tunggu agar baris data di halaman aktif siap
                for _ in range(30):
                    rows_ready = _safe_evaluate(page, """() => {
                        const trs = document.querySelectorAll('#table tbody tr, table tbody tr');
                        if (trs.length === 0 || document.querySelector('.dataTables_empty')) return 0;
                        return trs.length;
                    }""") or 0
                    if rows_ready > 0:
                        break
                    page.wait_for_timeout(1000)

                # Re-evaluasi total data jika saat pre-check awal tabel belum selesai dimuat
                if _p3ste_state["total"] <= 10:
                    late_diag = _safe_evaluate(page, r"""() => {
                        let total = 0;
                        try {
                            if (typeof $ !== 'undefined' && $.fn && $.fn.DataTable) {
                                const tbls = Array.from(document.querySelectorAll('table'));
                                for (const t of tbls) {
                                    if ($.fn.DataTable.isDataTable(t)) {
                                        const info = $(t).DataTable().page.info();
                                        if (info && info.recordsDisplay > 0) total = info.recordsDisplay;
                                        else if (info && info.recordsTotal > 0) total = info.recordsTotal;
                                        if (total > 0) break;
                                    }
                                }
                            }
                        } catch (e) {}
                        const infoEl = document.querySelector('.dataTables_info, #table_info, [id*="_info"]');
                        const infoText = infoEl ? infoEl.innerText : null;
                        if (!total && infoText) {
                            const m = infoText.match(/(?:dari|of)\s+([\d.,]+)/i);
                            if (m) total = parseInt(m[1].replace(/[.,]/g, ''), 10) || 0;
                        }
                        return { info: infoText, total: total };
                    }""") or {}
                    late_total = late_diag.get("total", 0)
                    if late_total > _p3ste_state["total"]:
                        _p3ste_state["total"] = late_total
                        if late_diag.get("info"):
                            _add_p3ste_log("info", f"Status Tabel: {late_diag['info']}")
                        _add_p3ste_log("info", f"📊 Terdeteksi target total: {late_total} file checklist.")

                # Pastikan cookie Requests session selalu up-to-date
                try:
                    cur_cookies = context.cookies(["https://p3-ste.kai.id"])
                    for cc in cur_cookies:
                        session.cookies.set(cc["name"], cc["value"], domain="p3-ste.kai.id")
                except Exception:
                    pass

                # Ekstrak ID/Link PDF valid (6-8 digit ID checklist)
                pdf_items = _safe_evaluate(page, r"""(typeName) => {
                    const items = [];
                    const seen = new Set();

                    function extractRowDate(tr) {
                        if (!tr) return '';
                        const tds = tr.querySelectorAll('td');
                        for (let i = 0; i < Math.min(tds.length, 4); i++) {
                            const txt = (tds[i].innerText || '').trim();
                            const dm = txt.match(/(\d{2})[/-](\d{2})[/-](\d{4})/);
                            if (dm) {
                                return `${dm[1]}-${dm[2]}-${dm[3]}`;
                            }
                        }
                        return '';
                    }
                    
                    // 1. Ekstrak dari link atau button cetak
                    const els = document.querySelectorAll('#table tbody tr a, #table tbody tr button, #table tbody tr [onclick], table tbody tr a, table tbody tr button');
                    els.forEach(el => {
                        const href = el.getAttribute('href') || '';
                        const onclick = el.getAttribute('onclick') || '';
                        const dataUrl = el.getAttribute('data-url') || el.getAttribute('data-href') || '';
                        const dataId = el.getAttribute('data-id') || '';
                        const combined = `${href} ${onclick} ${dataUrl} ${dataId}`;
                        
                        const m = combined.match(/exports\/pdf\/(\d{4,8})/i) || combined.match(/checklist.*?(\d{5,8})/i) || onclick.match(/['"](\d{5,8})['"]/);
                        let fid = null;
                        if (m) {
                            fid = m[1];
                        } else if (/^\d{5,8}$/.test(dataId)) {
                            fid = dataId;
                        }

                        if (fid && !seen.has(fid)) {
                            seen.add(fid);
                            const rowDate = extractRowDate(el.closest('tr'));
                            items.push({
                                id: fid,
                                url: `https://p3-ste.kai.id/cetak_checklist/report/${typeName}/exports/pdf/${fid}?false`,
                                date: rowDate
                            });
                        }
                    });
                    
                    // 2. Fallback: Ekstrak dari teks ID 6 digit di dalam baris tabel
                    if (items.length === 0) {
                        document.querySelectorAll('#table tbody tr, table tbody tr').forEach(tr => {
                            if (tr.querySelector('.dataTables_empty')) return;
                            const txt = tr.innerText || '';
                            const m = txt.match(/\b(\d{6,8})\b/);
                            if (m && !seen.has(m[1])) {
                                seen.add(m[1]);
                                const rowDate = extractRowDate(tr);
                                items.push({
                                    id: m[1],
                                    url: `https://p3-ste.kai.id/cetak_checklist/report/${typeName}/exports/pdf/${m[1]}?false`,
                                    date: rowDate
                                });
                            }
                        });
                    }
                    
                    return items;
                }""", type_name) or []

                # Filter item baru yang belum diunduh
                new_page_pdfs = [item for item in pdf_items if item["id"] not in downloaded_ids]
                _add_p3ste_log("info", f"Halaman {page_index}: Ditemukan {len(new_page_pdfs)} file PDF.")

                if len(new_page_pdfs) == 0:
                    # Beri kesempatan sekali lagi jika target data belum tercapai
                    if _p3ste_state["total"] > 0 and total_downloaded < _p3ste_state["total"]:
                        page.wait_for_timeout(2500)
                        pdf_items_retry = _safe_evaluate(page, r"""(typeName) => {
                            const items = [];
                            const seen = new Set();

                            function extractRowDate(tr) {
                                if (!tr) return '';
                                const tds = tr.querySelectorAll('td');
                                for (let i = 0; i < Math.min(tds.length, 4); i++) {
                                    const txt = (tds[i].innerText || '').trim();
                                    const dm = txt.match(/(\d{2})[/-](\d{2})[/-](\d{4})/);
                                    if (dm) {
                                        return `${dm[1]}-${dm[2]}-${dm[3]}`;
                                    }
                                }
                                return '';
                            }

                            const els = document.querySelectorAll('#table tbody tr a, #table tbody tr button, #table tbody tr [onclick], table tbody tr a, table tbody tr button');
                            els.forEach(el => {
                                const href = el.getAttribute('href') || '';
                                const onclick = el.getAttribute('onclick') || '';
                                const dataUrl = el.getAttribute('data-url') || el.getAttribute('data-href') || '';
                                const dataId = el.getAttribute('data-id') || '';
                                const combined = `${href} ${onclick} ${dataUrl} ${dataId}`;
                                
                                const m = combined.match(/exports\/pdf\/(\d{4,8})/i) || combined.match(/checklist.*?(\d{5,8})/i) || onclick.match(/['"](\d{5,8})['"]/);
                                let fid = null;
                                if (m) {
                                    fid = m[1];
                                } else if (/^\d{5,8}$/.test(dataId)) {
                                    fid = dataId;
                                }

                                if (fid && !seen.has(fid)) {
                                    seen.add(fid);
                                    const rowDate = extractRowDate(el.closest('tr'));
                                    items.push({
                                        id: fid,
                                        url: `https://p3-ste.kai.id/cetak_checklist/report/${typeName}/exports/pdf/${fid}?false`,
                                        date: rowDate
                                    });
                                }
                            });
                            if (items.length === 0) {
                                document.querySelectorAll('#table tbody tr, table tbody tr').forEach(tr => {
                                    if (tr.querySelector('.dataTables_empty')) return;
                                    const txt = tr.innerText || '';
                                    const m = txt.match(/\b(\d{6,8})\b/);
                                    if (m && !seen.has(m[1])) {
                                        seen.add(m[1]);
                                        const rowDate = extractRowDate(tr);
                                        items.push({
                                            id: m[1],
                                            url: `https://p3-ste.kai.id/cetak_checklist/report/${typeName}/exports/pdf/${m[1]}?false`,
                                            date: rowDate
                                        });
                                    }
                                });
                            }
                            return items;
                        }""", type_name) or []
                        new_page_pdfs = [item for item in pdf_items_retry if item["id"] not in downloaded_ids]
                        if len(new_page_pdfs) > 0:
                            _add_p3ste_log("info", f"Halaman {page_index} (Retry): Ditemukan {len(new_page_pdfs)} file PDF.")

                    if len(new_page_pdfs) == 0:
                        _add_p3ste_log("info", "Tidak ada file PDF baru pada halaman ini. Selesai.")
                        break

                downloaded_on_this_page = 0
                for item in new_page_pdfs:
                    if _p3ste_state["cancelled"]: break
                    fid = item["id"]
                    pdf_url = item["url"]
                    downloaded_ids.add(fid)
                    
                    total_downloaded += 1
                    _p3ste_state["current"] = total_downloaded

                    # 1. Cek dari file checkpoint
                    cached_entry = checkpoint_data.get(str(fid))
                    if cached_entry:
                        c_name = cached_entry.get("name", f"checklist_{fid}.pdf")
                        c_path = os.path.join(target_folder, c_name)
                        if c_name not in session_filenames and os.path.isfile(c_path) and os.path.getsize(c_path) > 1000:
                            fsize = os.path.getsize(c_path)
                            _p3ste_state["downloaded_files"].append({
                                "name": c_name,
                                "path": c_path,
                                "size": fsize
                            })
                            session_filenames.add(c_name)
                            _add_p3ste_log("info", f"⏭️ [{total_downloaded}] {c_name} (Sudah ada, dilewati)")
                            continue

                    # 2. Cek apakah file fisik checklist_{fid}.pdf sudah ada di folder
                    default_fn = f"checklist_{fid}.pdf"
                    default_path = os.path.join(target_folder, default_fn)
                    if default_fn not in session_filenames and os.path.isfile(default_path) and os.path.getsize(default_path) > 1000:
                        fsize = os.path.getsize(default_path)
                        checkpoint_data[str(fid)] = {"name": default_fn, "size": fsize}
                        _p3ste_state["downloaded_files"].append({
                            "name": default_fn,
                            "path": default_path,
                            "size": fsize
                        })
                        session_filenames.add(default_fn)
                        _add_p3ste_log("info", f"⏭️ [{total_downloaded}] {default_fn} (Sudah ada di folder, dilewati)")
                        continue

                    # Unduh via context.request dengan Retry Otomatis
                    fn = default_fn
                    download_success = False
                    last_err = ""
                    max_attempts = 4

                    for attempt in range(max_attempts):
                        if _p3ste_state["cancelled"]: break
                        try:
                            fresp = context.request.get(pdf_url, timeout=35000)
                            if fresp.status == 200:
                                body = fresp.body()
                                if body[:4] == b"%PDF":
                                    cd = fresp.headers.get("content-disposition", "")
                                    if "filename=" in cd:
                                        cd_fn = re.search(r'filename=["\']?([^"\';]+)["\']?', cd)
                                        if cd_fn:
                                            fn = cd_fn.group(1).strip().strip('"').strip("'")

                                    # Koreksi tanggal filename jika berbeda dari kolom Tanggal tabel web
                                    table_date = item.get("date")
                                    corrected_fn, orig_date = _correct_filename_date(fn, table_date)
                                    if orig_date:
                                        _add_p3ste_log("warn", f"⚠️ Koreksi Tanggal [{orig_date} → {table_date}]: Nama file server '{fn}' disesuaikan dengan tanggal tabel web.")
                                        fn = corrected_fn

                                    fn, out_path = _get_unique_p3ste_filename(target_folder, fn, session_filenames)

                                    with open(out_path, "wb") as pf:
                                        pf.write(body)

                                    file_size = len(body)
                                    session_filenames.add(fn)
                                    checkpoint_data[str(fid)] = {"name": fn, "size": file_size}
                                    try:
                                        with open(checkpoint_file, "w", encoding="utf-8") as cf:
                                            json.dump(checkpoint_data, cf, indent=2)
                                    except Exception:
                                        pass

                                    _p3ste_state["downloaded_files"].append({
                                        "name": fn,
                                        "path": out_path,
                                        "size": file_size
                                    })
                                    retry_tag = f" (setelah coba ulang ke-{attempt})" if attempt > 0 else ""
                                    _add_p3ste_log("success", f"✓ [{total_downloaded}] Tersimpan: {fn} ({file_size // 1024} KB){retry_tag}")
                                    download_success = True
                                    downloaded_on_this_page += 1
                                    break
                                else:
                                    last_err = "Bukan file PDF valid"
                            elif fresp.status in (500, 502, 503, 504, 429, 408):
                                last_err = f"HTTP {fresp.status}"
                                if attempt < max_attempts - 1:
                                    sleep_sec = 2.0 * (attempt + 1)
                                    _add_p3ste_log("warn", f"⚠️ [{total_downloaded}] {fn}: {last_err} - Server sibuk, mencoba ulang ({attempt + 1}/{max_attempts}) dalam {sleep_sec:.0f} detik...")
                                    time.sleep(sleep_sec)
                                    continue
                            else:
                                last_err = f"HTTP {fresp.status}"
                                break
                        except Exception as fe:
                            last_err = str(fe)
                            if "has been closed" in last_err.lower() or "target closed" in last_err.lower():
                                raise Exception("Jendela browser Edge ditutup paksa saat pengunduhan berlangsung. Silakan klik Mulai Download kembali untuk melanjutkan dari checkpoint.")
                            if attempt < max_attempts - 1:
                                sleep_sec = 2.0 * (attempt + 1)
                                _add_p3ste_log("warn", f"⚠️ [{total_downloaded}] {fn}: Error koneksi ({last_err}) - Mencoba ulang ({attempt + 1}/{max_attempts}) dalam {sleep_sec:.0f} detik...")
                                time.sleep(sleep_sec)
                                continue

                    if not download_success and not _p3ste_state["cancelled"]:
                        _add_p3ste_log("error", f"✗ [{total_downloaded}] {fn}: {last_err} (Gagal pada putaran pertama, akan dicoba ulang di akhir)")
                        failed_queue.append({
                            "id": fid,
                            "url": pdf_url,
                            "default_fn": default_fn,
                            "last_err": last_err,
                            "date": item.get("date")
                        })

                    if total_downloaded > _p3ste_state["total"]:
                        _p3ste_state["total"] = total_downloaded

                old_first_id = new_page_pdfs[0]["id"] if new_page_pdfs else None

                # Jika seluruh file di halaman ini dilewati secara instan dari checkpoint (<10ms),
                # beri jeda stabilisasi 2 detik agar DataTables selesai mengikat event pagination.
                if downloaded_on_this_page == 0:
                    page.wait_for_timeout(2000)

                # Pengecekan halaman selanjutnya (Next Page) dengan retry cerdas (selalu 3x)
                max_next_retries = 3
                page_changed = False

                for next_attempt in range(max_next_retries):
                    if _p3ste_state["cancelled"]:
                        break

                    can_go_next = _safe_evaluate(page, """() => {
                        // 1. Prioritaskan DataTables API langsung jika tersedia
                        try {
                            if (typeof $ !== 'undefined' && $.fn && $.fn.DataTable) {
                                const tables = Array.from(document.querySelectorAll('table'));
                                for (const tbl of tables) {
                                    if ($.fn.DataTable.isDataTable(tbl)) {
                                        const dt = $(tbl).DataTable();
                                        const info = dt.page.info();
                                        if (info && info.pages > 1 && info.page < info.pages - 1) {
                                            dt.page('next').draw('page');
                                            return { hasNext: true, page: info.page + 2, totalPages: info.pages, method: 'api' };
                                        }
                                    }
                                }
                            }
                        } catch (e) {}
                        // 2. Fallback Cek DOM Tombol Next spesifik DataTables
                        const nextLi = document.querySelector('li#table_next, #table_next, li.paginate_button.next, #tblData_next');
                        if (nextLi && !nextLi.classList.contains('disabled') && nextLi.getAttribute('aria-disabled') !== 'true') {
                            const a = nextLi.querySelector('a') || nextLi;
                            a.click();
                            return { hasNext: true, method: 'dom' };
                        }
                        return { hasNext: false };
                    }""") or {}

                    if not can_go_next.get("hasNext"):
                        # Jika menurut indikator halaman habis tapi target belum terpenuhi, tunggu 2.5s lalu periksa ulang
                        if _p3ste_state["total"] > 0 and total_downloaded < _p3ste_state["total"] and next_attempt < max_next_retries - 1:
                            _add_p3ste_log("warn", f"⏳ Memverifikasi status pagination ({total_downloaded}/{_p3ste_state['total']} data)...")
                            page.wait_for_timeout(2500)
                            continue
                        _add_p3ste_log("info", "Mencapai halaman terakhir.")
                        break

                    if next_attempt == 0:
                        _add_p3ste_log("info", f"Mengeklik 'Selanjutnya' ke Halaman {page_index + 1}...")
                    else:
                        _add_p3ste_log("warn", f"Mencoba ulang klik 'Selanjutnya' ke Halaman {page_index + 1} (Percobaan {next_attempt + 1}/{max_next_retries})...")

                    # Tunggu proses AJAX DataTables selesai memuat halaman berikutnya (hingga 90 detik)
                    for wait_sec in range(90):
                        if _p3ste_state["cancelled"]: break
                        page.wait_for_timeout(1000)

                        # Re-trigger hanya pada detik ke-45 (agar tidak membatalkan AJAX P3-STE yang memakan 25-35 detik)
                        if wait_sec == 45:
                            _safe_evaluate(page, """() => {
                                try {
                                    if (typeof $ !== 'undefined' && $.fn && $.fn.DataTable) {
                                        const tables = Array.from(document.querySelectorAll('table'));
                                        for (const tbl of tables) {
                                            if ($.fn.DataTable.isDataTable(tbl)) {
                                                $(tbl).DataTable().page('next').draw('page');
                                                return;
                                            }
                                        }
                                    }
                                } catch (e) {}
                                const nextLi = document.querySelector('li#table_next, #table_next, li.paginate_button.next, #tblData_next');
                                if (nextLi && !nextLi.classList.contains('disabled')) {
                                    const a = nextLi.querySelector('a') || nextLi;
                                    a.click();
                                }
                            }""")

                        cur_first_id = _safe_evaluate(page, r"""() => {
                            const tr = document.querySelector('#table tbody tr, table tbody tr');
                            if (!tr || tr.querySelector('.dataTables_empty')) return null;
                            const m = (tr.innerHTML || '').match(/exports\/pdf\/(\d{4,8})|['"](\d{5,8})['"]/i);
                            if (m) return m[1] || m[2];
                            const txtMatch = (tr.innerText || '').match(/\b(\d{6,8})\b/);
                            return txtMatch ? txtMatch[1] : null;
                        }""")

                        if cur_first_id and cur_first_id != old_first_id:
                            page_changed = True
                            break

                    if page_changed:
                        break

                if not page_changed:
                    if _p3ste_state["total"] > 0 and total_downloaded < _p3ste_state["total"]:
                        _add_p3ste_log("warn", f"⚠️ Halaman berikutnya tidak merespons setelah beberapa percobaan. Pengunduhan diselesaikan pada {total_downloaded} dari target {_p3ste_state['total']} data.")
                    else:
                        _add_p3ste_log("info", "Halaman berikutnya tidak memuat data baru. Selesai.")
                    break

                page_index += 1
                page.wait_for_timeout(1500)

            # Putaran Kedua: Coba ulang file yang sempat gagal pada putaran pertama
            if failed_queue and not _p3ste_state["cancelled"]:
                _add_p3ste_log("warn", f"🔄 Ditemukan {len(failed_queue)} file yang sempat gagal. Memulai putaran coba ulang otomatis...")
                time.sleep(2.5)
                still_failed = []
                for idx, failed_item in enumerate(failed_queue, 1):
                    if _p3ste_state["cancelled"]: break
                    ffid = failed_item["id"]
                    furl = failed_item["url"]
                    ffn = failed_item["default_fn"]
                    _add_p3ste_log("info", f"🔄 [Coba Ulang {idx}/{len(failed_queue)}] ID {ffid}...")

                    retry_ok = False
                    for r_att in range(3):
                        if _p3ste_state["cancelled"]: break
                        try:
                            fresp = context.request.get(furl, timeout=35000)
                            if fresp.status == 200:
                                body = fresp.body()
                                if body[:4] == b"%PDF":
                                    cd = fresp.headers.get("content-disposition", "")
                                    if "filename=" in cd:
                                        cd_fn = re.search(r'filename=["\']?([^"\';]+)["\']?', cd)
                                        if cd_fn:
                                            ffn = cd_fn.group(1).strip().strip('"').strip("'")

                                    # Koreksi tanggal filename jika berbeda dari kolom Tanggal tabel web
                                    table_date = failed_item.get("date")
                                    corrected_ffn, orig_date = _correct_filename_date(ffn, table_date)
                                    if orig_date:
                                        _add_p3ste_log("warn", f"⚠️ Koreksi Tanggal [{orig_date} → {table_date}]: Nama file server '{ffn}' disesuaikan dengan tanggal tabel web.")
                                        ffn = corrected_ffn

                                    ffn, out_path = _get_unique_p3ste_filename(target_folder, ffn, session_filenames)

                                    with open(out_path, "wb") as pf:
                                        pf.write(body)

                                    file_size = len(body)
                                    session_filenames.add(ffn)
                                    checkpoint_data[str(ffid)] = {"name": ffn, "size": file_size}
                                    try:
                                        with open(checkpoint_file, "w", encoding="utf-8") as cf:
                                            json.dump(checkpoint_data, cf, indent=2)
                                    except Exception:
                                        pass

                                    _p3ste_state["downloaded_files"].append({
                                        "name": ffn,
                                        "path": out_path,
                                        "size": file_size
                                    })
                                    _add_p3ste_log("success", f"✓ Berhasil diunduh pada putaran ulang: {ffn} ({file_size // 1024} KB)")
                                    retry_ok = True
                                    break
                                else:
                                    time.sleep(2.0)
                            else:
                                time.sleep(2.0)
                        except Exception:
                            time.sleep(2.0)

                    if not retry_ok:
                        still_failed.append(failed_item)

                if still_failed:
                    _add_p3ste_log("error", f"❌ {len(still_failed)} file tetap gagal diunduh setelah coba ulang: {', '.join(str(x['id']) for x in still_failed[:5])}")
                else:
                    _add_p3ste_log("success", "🎉 Semua file yang sempat gagal berhasil diunduh 100% pada putaran ulang!")

            if _p3ste_state["cancelled"]:
                _add_p3ste_log("warn", "🛑 Pengunduhan dihentikan oleh pengguna.")
            else:
                success_count = len(_p3ste_state['downloaded_files'])
                target_tot = _p3ste_state['total']
                if target_tot > 0 and success_count >= target_tot:
                    _add_p3ste_log("success", f"🎉 Selesai! Semua {success_count} dari {target_tot} file PDF berhasil diunduh 100%.")
                else:
                    _add_p3ste_log("success", f"Selesai! Berhasil mengunduh total {success_count} file PDF dari semua halaman.")

            try:
                context.close()
            except Exception:
                pass
            _current_playwright_context = None

    except Exception as e:
        if _p3ste_state["cancelled"]:
            _add_p3ste_log("warn", "🛑 Semua proses berhasil dihentikan oleh pengguna.")
        else:
            _p3ste_state["error"] = str(e)
            _add_p3ste_log("error", f"FATAL ERROR: {e}")
    finally:
        _current_playwright_context = None
        _p3ste_state["running"] = False
        _cleanup_p3ste_browser_profile()


def on_restored():
    """Keep state intact. No page reload — env flags already prevent blank screen."""
    global _was_minimized
    _log(f"🟢 EVENT: restored (was_minimized={_was_minimized})")
    _was_minimized = False


def _pick_folder_native():
    """Buka dialog pemilihan folder di Windows:
    1. Tkinter askdirectory (Topmost, native OS dialog, paling stabil & cepat)
    2. pywebview create_file_dialog (jika native window aktif)
    3. PowerShell WinForms fallback
    """
    # 1. Tkinter (Topmost dialog)
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        folder = filedialog.askdirectory(title="Pilih Folder Penyimpanan PDF Rekap")
        root.destroy()
        if folder and os.path.isdir(folder):
            return os.path.normpath(folder)
    except Exception as e:
        _log(f"Tkinter folder picker notice: {e}")

    # 2. Coba via pywebview jika window aktif
    try:
        if getattr(webview, 'windows', None) and len(webview.windows) > 0:
            dialog_type = getattr(webview.FileDialog, 'FOLDER', getattr(webview, 'FOLDER_DIALOG', 2))
            result = webview.windows[0].create_file_dialog(dialog_type)
            if result and len(result) > 0 and result[0]:
                return os.path.normpath(result[0])
    except Exception as e:
        _log(f"WebView file dialog notice: {e}")

    # 3. Fallback via PowerShell WinForms
    try:
        import subprocess
        ps_cmd = [
            "powershell.exe",
            "-NoProfile",
            "-Command",
            "Add-Type -AssemblyName System.Windows.Forms; $f = New-Object System.Windows.Forms.FolderBrowserDialog; $f.Description = 'Pilih Folder Penyimpanan'; $f.ShowNewFolderButton = $true; if($f.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK){ [Console]::Out.Write($f.SelectedPath) }"
        ]
        res = subprocess.run(
            ps_cmd,
            capture_output=True,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        )
        path = res.stdout.strip()
        if path and os.path.isdir(path):
            return os.path.normpath(path)
    except Exception as e:
        _log(f"PowerShell folder dialog fallback error: {e}")

    return None


def _pick_file_native():
    """Buka dialog pemilihan file di Windows:
    1. Tkinter askopenfilename (Topmost)
    2. pywebview create_file_dialog OPEN
    """
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        fpath = filedialog.askopenfilename(
            title="Pilih Berkas PDF atau schedule.json",
            filetypes=[("PDF atau JSON", "*.pdf;*.json"), ("Semua Berkas", "*.*")]
        )
        root.destroy()
        if fpath and os.path.isfile(fpath):
            return os.path.normpath(fpath)
    except Exception as e:
        _log(f"Tkinter file picker notice: {e}")

    try:
        if getattr(webview, 'windows', None) and len(webview.windows) > 0:
            dialog_type = getattr(webview.FileDialog, 'OPEN', getattr(webview, 'OPEN_DIALOG', 10))
            result = webview.windows[0].create_file_dialog(
                dialog_type,
                file_types=("PDF & JSON (*.pdf;*.json)", "Semua Berkas (*.*)")
            )
            if result and len(result) > 0 and result[0]:
                return os.path.normpath(result[0])
    except Exception as e:
        _log(f"WebView file dialog notice: {e}")

    return None


def _pick_files_native():
    """Buka dialog pemilihan multiple file di Windows:
    1. Tkinter askopenfilenames (Topmost)
    2. pywebview create_file_dialog OPEN allow_multiple=True
    """
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        fpaths = filedialog.askopenfilenames(
            title="Pilih Berkas PDF",
            filetypes=[("Berkas PDF", "*.pdf"), ("Semua Berkas", "*.*")]
        )
        root.destroy()
        if fpaths:
            return [os.path.normpath(f) for f in fpaths if os.path.isfile(f)]
    except Exception as e:
        _log(f"Tkinter multi file picker notice: {e}")

    try:
        if getattr(webview, 'windows', None) and len(webview.windows) > 0:
            dialog_type = getattr(webview.FileDialog, 'OPEN', getattr(webview, 'OPEN_DIALOG', 10))
            result = webview.windows[0].create_file_dialog(
                dialog_type,
                allow_multiple=True,
                file_types=("Berkas PDF (*.pdf)", "Semua Berkas (*.*)")
            )
            if result:
                if isinstance(result, (list, tuple)):
                    return [os.path.normpath(f) for f in result if os.path.isfile(f)]
                elif os.path.isfile(result):
                    return [os.path.normpath(result)]
    except Exception as e:
        _log(f"WebView multi file dialog notice: {e}")

    return []



def _pick_json_file_native(title="Pilih Berkas Cadangan Preset (*.json)"):
    """Buka dialog pemilihan berkas JSON cadangan di Windows."""
    # 1. Tkinter (Topmost)
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        fpath = filedialog.askopenfilename(
            title=title,
            filetypes=[("JSON Files", "*.json"), ("Semua Berkas", "*.*")]
        )
        root.destroy()
        if fpath and os.path.isfile(fpath):
            return os.path.normpath(fpath)
    except Exception as e:
        _log(f"Tkinter JSON picker notice: {e}")

    # 2. pywebview file dialog
    try:
        if getattr(webview, 'windows', None) and len(webview.windows) > 0:
            dialog_type = getattr(webview.FileDialog, 'OPEN', getattr(webview, 'OPEN_DIALOG', 10))
            result = webview.windows[0].create_file_dialog(
                dialog_type,
                file_types=("JSON Files (*.json)", "Semua Berkas (*.*)")
            )
            if result and len(result) > 0 and result[0]:
                return os.path.normpath(result[0])
    except Exception as e:
        _log(f"WebView JSON dialog notice: {e}")

    # 3. PowerShell WinForms OpenFileDialog fallback
    try:
        ps_cmd = [
            "powershell.exe",
            "-NoProfile",
            "-Sta",
            "-Command",
            f"Add-Type -AssemblyName System.Windows.Forms; $f = New-Object System.Windows.Forms.OpenFileDialog; $f.Title = '{title}'; $f.Filter = 'JSON Files (*.json)|*.json|All files (*.*)|*.*'; if($f.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK){{ [Console]::Out.Write($f.FileName) }}"
        ]
        res = subprocess.run(
            ps_cmd,
            capture_output=True,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        )
        path = res.stdout.strip()
        if path and os.path.isfile(path):
            return os.path.normpath(path)
    except Exception as ps_err:
        _log(f"PowerShell JSON open dialog notice: {ps_err}")

    return None


def _save_file_dialog_native(default_name):
    """Opens a native Windows Save As file dialog."""
    ext = os.path.splitext(default_name)[1].lower()
    if ext == ".xlsx":
        webview_types = ('Excel Files (*.xlsx)', 'All files (*.*)')
        tk_types = [("Excel Files", "*.xlsx"), ("All Files", "*.*")]
        ps_filter = 'Excel Files (*.xlsx)|*.xlsx|All files (*.*)|*.*'
    elif ext == ".json":
        webview_types = ('JSON Files (*.json)', 'All files (*.*)')
        tk_types = [("JSON Files", "*.json"), ("All Files", "*.*")]
        ps_filter = 'JSON Files (*.json)|*.json|All files (*.*)|*.*'
    else:
        webview_types = ('All files (*.*)',)
        tk_types = [("All Files", "*.*")]
        ps_filter = 'All files (*.*)|*.*'

    # 1. Coba via pywebview jika window aktif (Native Windows FileDialog)
    try:
        if getattr(webview, 'windows', None) and len(webview.windows) > 0:
            dialog_type = getattr(webview.FileDialog, 'SAVE', getattr(webview, 'SAVE_DIALOG', 30))
            result = webview.windows[0].create_file_dialog(
                dialog_type,
                save_filename=default_name,
                file_types=webview_types
            )
            if result:
                if isinstance(result, (list, tuple)) and len(result) > 0:
                    return os.path.normpath(result[0])
                elif isinstance(result, str):
                    return os.path.normpath(result)
            return None
    except Exception as e:
        _log(f"WebView save dialog notice: {e}")

    # 2. Coba via Tkinter (Dev mode jika tkinter tersedia)
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.asksaveasfilename(
            initialfile=default_name,
            filetypes=tk_types,
            defaultextension=ext
        )
        root.destroy()
        if path:
            return os.path.normpath(path)
    except Exception as e:
        _log(f"Tkinter save dialog notice: {e}")

    # 3. Fallback via PowerShell WinForms
    try:
        ps_cmd = [
            "powershell.exe",
            "-NoProfile",
            "-Sta",
            "-Command",
            f"Add-Type -AssemblyName System.Windows.Forms; $f = New-Object System.Windows.Forms.SaveFileDialog; $f.FileName = '{default_name}'; $f.Filter = '{ps_filter}'; if($f.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK){{ [Console]::Out.Write($f.FileName) }}"
        ]
        res = subprocess.run(
            ps_cmd,
            capture_output=True,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        )
        path = res.stdout.strip()
        if path:
            return os.path.normpath(path)
    except Exception as ps_err:
        _log(f"PowerShell save dialog notice: {ps_err}")

    return None


def get_active_pegawai_config(preset_id=None):
    """
    Mengambil konfigurasi pegawai aktif berdasarkan preset_id (jika diberikan),
    atau active_preset_id dari employee_presets.json, atau fallback ke daftar_pegawai.json.
    """
    cand_presets = [
        os.path.join(APP_DATA_DIR, "employee_presets.json"),
        os.path.join(ENGINE_DIR, "employee_presets.json"),
        os.path.join(BASE_DIR, "config", "employee_presets.json"),
    ]
    presets_data = {}
    for cp in cand_presets:
        if os.path.isfile(cp):
            try:
                with open(cp, "r", encoding="utf-8") as f:
                    presets_data = json.load(f)
                break
            except Exception:
                pass

    target_pid = preset_id or presets_data.get("active_preset_id")
    if target_pid and "presets" in presets_data:
        for p in presets_data["presets"]:
            if p.get("id") == target_pid and p.get("data"):
                return p["data"], p.get("name", "Preset Kustom")

    cand_pegawai = [
        os.path.join(APP_DATA_DIR, "daftar_pegawai.json"),
        os.path.join(ENGINE_DIR, "daftar_pegawai.json"),
        os.path.join(BASE_DIR, "config", "daftar_pegawai.json"),
    ]
    for cp in cand_pegawai:
        if os.path.isfile(cp):
            try:
                with open(cp, "r", encoding="utf-8") as f:
                    d = json.load(f)
                    first_pname = presets_data.get("presets", [{}])[0].get("name", "Standar") if presets_data.get("presets") else "Standar"
                    return d, first_pname
            except Exception:
                pass

    try:
        from timemark_engine.employee_manager import load_pegawai_config
        return load_pegawai_config(), "Standar"
    except Exception:
        return {}, "Standar"


def _resolve_photo_directories(folder_path: str) -> tuple[str, str, str]:
    """
    Menentukan direktori root, direktori foto mentah (03_export_foto / 03_photos_export),
    dan direktori foto editan (04_photos_edited) tanpa membuat folder baru secara paksa
    (read-only resolution agar pemilihan folder PDF 2026/2025 tidak memunculkan folder 03/04).
    """
    if not folder_path:
        folder_path = os.path.join(os.path.expanduser("~"), "Documents", "Sintelis", "03_export_foto")

    norm = os.path.normpath(folder_path)
    base_name = os.path.basename(norm).lower()

    if base_name in ("03_export_foto", "03_photos_export", "04_photos_edited", "04_foto_edited", "04_time", "04_koordinat", "05_pdf_merged"):
        export_root = os.path.dirname(norm)
    else:
        export_root = norm

    # 1. Cari path folder 03 (foto mentah) tanpa membuat direktori di disk
    dir_raw = None
    for cand_name in ["03_export_foto", "03_photos_export"]:
        cand = os.path.join(export_root, cand_name)
        if os.path.isdir(cand):
            dir_raw = cand
            break

    if not dir_raw:
        if base_name in ("03_export_foto", "03_photos_export") and os.path.isdir(norm):
            dir_raw = norm
        else:
            dir_raw = os.path.join(export_root, "03_export_foto")

    # 2. Cari path folder 04 (foto editan) tanpa membuat direktori di disk
    dir_edited = None
    for cand_name in ["04_photos_edited", "04_foto_edited"]:
        cand = os.path.join(export_root, cand_name)
        if os.path.isdir(cand):
            dir_edited = cand
            break

    if not dir_edited:
        dir_edited = os.path.join(export_root, "04_photos_edited")

    return export_root, dir_raw, dir_edited


class ApiHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP handler: serve static files + /api/* endpoints"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIST_DIR, **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/p3ste/status":
            self._json(_p3ste_state)
        elif parsed.path == "/api/accounts":
            self._handle_get_accounts()
        elif parsed.path == "/api/get-file":
            self._handle_get_file(parsed)
        elif parsed.path == "/api/list-folder-pdfs":
            self._handle_list_folder_pdfs(parsed)
        elif parsed.path == "/api/timemark/status":
            self._json(pipeline_runner.get_state())
        elif parsed.path == "/api/timemark/photos":
            self._handle_timemark_photos(parsed)
        elif parsed.path == "/api/timemark/photo-file":
            self._handle_timemark_photo_file(parsed)
        elif parsed.path == "/api/timemark/schedule-list":
            self._handle_timemark_schedule_list(parsed)
        elif parsed.path == "/api/timemark/pegawai":
            self._handle_timemark_pegawai_get()
        elif parsed.path == "/api/version":
            self._json({"version": updater_engine.APP_VERSION, "name": "Sintelis Utility"})
        elif parsed.path == "/api/update/check":
            qs = urllib.parse.parse_qs(parsed.query)
            custom_url = qs.get("url", [None])[0]
            self._json(updater_engine.check_update(custom_url))
        elif parsed.path == "/api/update/progress":
            self._json(updater_engine.get_update_state())
        else:
            super().do_GET()

    def _handle_get_accounts(self):
        try:
            if os.path.isfile(ACCOUNTS_FILE):
                with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._json(data)
            else:
                self._json({"accounts": [], "selected_id": "acc_default"})
        except Exception as e:
            self._json({"error": str(e)}, 500)

    def _handle_save_accounts(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            data = json.loads(body)
            with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            self._json({"ok": True})
        except Exception as e:
            self._json({"error": str(e)}, 500)

    def _handle_get_file(self, parsed):
        try:
            qs = urllib.parse.parse_qs(parsed.query)
            file_path = qs.get("path", [""])[0]
            if not file_path or not os.path.isfile(file_path):
                self.send_error(404, "File tidak ditemukan")
                return
            with open(file_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self._json({"error": str(e)}, 500)

    def _handle_list_folder_pdfs(self, parsed):
        try:
            qs = urllib.parse.parse_qs(parsed.query)
            folder = qs.get("folder", [""])[0]
            if not folder or not os.path.isdir(folder):
                self._json({"files": []})
                return
            files = []
            for root, dirs, filenames in os.walk(folder):
                # Abaikan folder cadangan / sistem agar tidak terhitung ganda
                dirs[:] = [d for d in dirs if d.lower() not in ("backups", "_temp_merged", ".git", "node_modules")]
                for fn in sorted(filenames):
                    if fn.lower().endswith(".pdf"):
                        fp = os.path.join(root, fn)
                        if os.path.isfile(fp):
                            rel_p = os.path.relpath(fp, folder).replace("\\", "/")
                            files.append({
                                "name": fn,
                                "path": fp,
                                "relPath": rel_p,
                                "size": os.path.getsize(fp)
                            })
            self._json({"files": files})
        except Exception as e:
            self._json({"error": str(e)}, 500)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/select-folder":
            self._handle_select_folder()
        elif parsed.path == "/api/select-file":
            self._handle_select_file()
        elif parsed.path == "/api/accounts":
            self._handle_save_accounts()
        elif parsed.path == "/api/save-file":
            self._handle_save_file()
        elif parsed.path == "/api/save-dialog-file":
            self._handle_save_dialog_file()
        elif parsed.path == "/api/ocr":
            self._handle_ocr()
        elif parsed.path == "/api/p3ste/download":
            self._handle_p3ste_download()
        elif parsed.path == "/api/p3ste/status":
            self._json(_p3ste_state)
        elif parsed.path == "/api/p3ste/cancel":
            _cancel_all_processes()
            self._json({"ok": True})
        elif parsed.path == "/api/timemark/start":
            self._handle_timemark_start()
        elif parsed.path == "/api/timemark/cancel":
            pipeline_runner.cancel_pipeline()
            self._json({"ok": True})
        elif parsed.path == "/api/timemark/edit-time":
            self._handle_timemark_edit_time()
        elif parsed.path == "/api/timemark/process-single":
            self._handle_timemark_process_single()
        elif parsed.path == "/api/timemark/manual-edit":
            self._handle_timemark_manual_edit()
        elif parsed.path == "/api/timemark/remerge-single":
            self._handle_timemark_remerge_single()
        elif parsed.path == "/api/timemark/edit-coord":
            self._handle_timemark_edit_coord()
        elif parsed.path == "/api/timemark/replace-photo":
            self._handle_timemark_replace_photo()
        elif parsed.path == "/api/timemark/revert-photo":
            self._handle_timemark_revert_photo()
        elif parsed.path == "/api/timemark/swap-photo":
            self._handle_timemark_swap_photo()
        elif parsed.path == "/api/timemark/crop-collage-single":
            self._handle_timemark_crop_collage_single()
        elif parsed.path == "/api/timemark/pegawai":
            self._handle_timemark_pegawai_post()
        elif parsed.path == "/api/timemark/set-active-preset":
            self._handle_timemark_set_active_preset()
        elif parsed.path == "/api/timemark/export-presets":
            self._handle_timemark_export_presets()
        elif parsed.path == "/api/timemark/import-presets":
            self._handle_timemark_import_presets()
        elif parsed.path == "/api/timemark/koreksi-serat-optik":
            self._handle_timemark_koreksi_serat_optik()
        elif parsed.path == "/api/timemark/audit-personil":
            self._handle_timemark_audit_personil()
        elif parsed.path == "/api/timemark/export-tablo":
            self._handle_timemark_export_tablo()
        elif parsed.path == "/api/timemark/export-dinasan":
            self._handle_timemark_export_dinasan()
        elif parsed.path == "/api/timemark/open-file":
            self._handle_timemark_open_file()
        elif parsed.path == "/api/update/download":
            self._handle_update_download()
        elif parsed.path == "/api/update/apply":
            self._json(updater_engine.apply_update_and_restart())
        elif parsed.path == "/api/select-files":
            self._handle_select_files()
        elif parsed.path == "/api/timemark/export-schedule-excel":
            self._handle_timemark_export_schedule_excel()
        elif parsed.path == "/api/timemark/generate-schedule":
            self._handle_timemark_generate_schedule()
        elif parsed.path == "/api/personnel-changer/scan":
            self._handle_personnel_changer_scan()
        elif parsed.path == "/api/personnel-changer/apply":
            self._handle_personnel_changer_apply()
        elif parsed.path == "/api/date-changer/scan":
            self._handle_date_changer_scan()
        elif parsed.path == "/api/date-changer/apply":
            self._handle_date_changer_apply()
        else:
            self.send_error(404)

    def _handle_timemark_start(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            data = json.loads(body) if body else {}
            res = pipeline_runner.start_pipeline(
                data.get("sourceDir"),
                data.get("targetDir"),
                data.get("exportDir"),
                data.get("mergedDir"),
                data.get("steps"),
                data.get("mode", "dual"),
                data.get("overwriteOriginal", False),
                data.get("detector", "google_vision")
            )
            self._json(res)
        except Exception as e:
            _log(f"Timemark start error: {e}")
            self._json({"error": str(e)}, 500)

    def _handle_timemark_photos(self, parsed):
        try:
            qs = urllib.parse.parse_qs(parsed.query)
            folder = qs.get("folder", [""])[0]
            if not folder or not os.path.isdir(folder):
                self._json({"ok": True, "assets": []})
                return

            # Indeks berkas target dan tanggal dari schedule.json
            target_files_map = {}
            target_files_list = []
            schedule_date_map = {}
            seen_target_files = set()
            sched_candidates = [
                os.path.join(folder, "schedule.json"),
                os.path.join(os.path.dirname(folder), "schedule.json"),
                os.path.join(os.path.dirname(os.path.dirname(folder)), "schedule.json"),
                os.path.join(BASE_DIR, "schedule.json"),
                os.path.join(os.getcwd(), "schedule.json"),
            ]
            for sc_path in sched_candidates:
                if os.path.isfile(sc_path):
                    try:
                        with open(sc_path, "r", encoding="utf-8") as sf:
                            sdata = json.load(sf)
                        for item in sdata.get("schedules", []):
                            fn = item.get("file")
                            d_text = item.get("dateText") or item.get("iso_date") or ""
                            if not fn:
                                continue
                            if fn not in seen_target_files:
                                seen_target_files.add(fn)
                                target_files_list.append({
                                    "file": fn,
                                    "category": item.get("category", ""),
                                    "btp": item.get("btp", ""),
                                    "date": item.get("iso_date", "")
                                })
                            for k in ["identifier", "base_identifier"]:
                                ident = item.get(k)
                                if ident:
                                    norm_id = " ".join(re.sub(r'_\d{2}-\d{2}$', '', ident.strip().upper()).split())
                                    if norm_id not in target_files_map:
                                        target_files_map[norm_id] = []
                                    if fn not in target_files_map[norm_id]:
                                        target_files_map[norm_id].append(fn)
                                    if d_text and norm_id not in schedule_date_map:
                                        schedule_date_map[norm_id] = d_text
                        break
                    except Exception as e:
                        _log(f"Error reading schedule candidate {sc_path}: {e}")

            # Indeks berkas sumber dari pdf_photo_export_log.csv
            source_files_map = {}
            source_files_list = []
            seen_source_files = set()
            csv_candidates = [
                os.path.join(folder, "logs", "pdf_photo_export_log.csv"),
                os.path.join(os.path.dirname(folder), "logs", "pdf_photo_export_log.csv"),
                os.path.join(BASE_DIR, "logs", "pdf_photo_export_log.csv"),
                os.path.join(os.getcwd(), "logs", "pdf_photo_export_log.csv"),
            ]
            for c_path in csv_candidates:
                if os.path.isfile(c_path):
                    try:
                        import csv
                        with open(c_path, "r", encoding="utf-8", errors="ignore") as cf:
                            reader = csv.DictReader(cf)
                            for row in reader:
                                p_pdf = row.get("pdf")
                                p_name = row.get("asset_name")
                                if p_pdf and p_name:
                                    if p_pdf not in seen_source_files:
                                        seen_source_files.add(p_pdf)
                                        source_files_list.append(p_pdf)
                                    norm_p = " ".join(p_name.strip().upper().split())
                                    if norm_p not in source_files_map:
                                        source_files_map[norm_p] = p_pdf
                        break
                    except Exception as e:
                        _log(f"Error reading csv candidate {c_path}: {e}")

            # Resolusi terpusat folder 03 (foto mentah) dan 04 (foto editan)
            export_root, dir_raw, dir_edited = _resolve_photo_directories(folder)

            dir_time = os.path.join(export_root, "04_Time")
            dir_coord = os.path.join(export_root, "04_koordinat")

            # Kumpulkan semua folder aset unik: (btp, category, detail)
            asset_dict = {}

            # 1. Scan dari dir_raw (Foto Mentah) - Pastikan TIDAK PERNAH masuk ke subfolder 04_
            if os.path.isdir(dir_raw):
                for root, dirs, files in os.walk(dir_raw):
                    dirs[:] = [d for d in dirs if d.lower() not in (
                        "04_photos_edited", "04_foto_edited", "04_time", "04_koordinat", "05_pdf_merged", "backups", "_temp_merged", ".git", "node_modules"
                    )]
                    photo_files = [f for f in files if f.lower() in ("0.jpg", "50.jpg", "100.jpg")]
                    rel = os.path.relpath(root, dir_raw).replace("\\", "/")
                    parts = [p for p in rel.split("/") if p and p != "."]
                    if not parts or len(parts) < 2:
                        continue
                    # Jika masih memiliki sub-folder dan belum ada foto di folder ini, biarkan os.walk menyelam lebih dalam
                    if dirs and not photo_files:
                        continue
                    detail = parts[-1]
                    category = parts[-2] if len(parts) >= 2 else "ASET"
                    station = parts[-3] if len(parts) >= 3 else (parts[0] if len(parts) >= 1 else "STN")
                    key = (station.upper(), category.upper(), detail.upper())
                    if key not in asset_dict:
                        asset_dict[key] = {
                            "station": station,
                            "category": category,
                            "detail": detail,
                            "raw_dir": root,
                            "edited_dir": None,
                            "tim": ""
                        }

            # 2. Scan dari dir_edited jika ada (Foto Hasil Timemark)
            if os.path.isdir(dir_edited):
                for root, dirs, files in os.walk(dir_edited):
                    dirs[:] = [d for d in dirs if d.lower() not in (
                        "backups", "_temp_merged", ".git", "node_modules", "03_photos_export", "03_export_foto"
                    )]
                    photo_files = [f for f in files if f.lower() in ("0.jpg", "50.jpg", "100.jpg")]
                    rel = os.path.relpath(root, dir_edited).replace("\\", "/")
                    parts = [p for p in rel.split("/") if p and p != "."]
                    if not parts or len(parts) < 2:
                        continue
                    # Jika masih memiliki sub-folder dan belum ada foto di folder ini, biarkan os.walk menyelam lebih dalam
                    if dirs and not photo_files:
                        continue
                    detail = parts[-1]
                    category = parts[-2] if len(parts) >= 2 else "ASET"
                    station = parts[-3] if len(parts) >= 3 else (parts[0] if len(parts) >= 1 else "STN")
                    tim = ""
                    for p in parts:
                        if re.match(r"^tim[_\s]\d+$", p, re.IGNORECASE):
                            tim = p.replace("_", " ").title()
                            break

                    def _dir_latest_mtime(d_p):
                        if not d_p or not os.path.isdir(d_p):
                            return 0.0
                        mts = []
                        for _fn in ("0.jpg", "50.jpg", "100.jpg", "meta.json"):
                            _fp = os.path.join(d_p, _fn)
                            if os.path.isfile(_fp):
                                try:
                                    mts.append(os.path.getmtime(_fp))
                                except Exception:
                                    pass
                        return max(mts) if mts else 0.0

                    key = (station.upper(), category.upper(), detail.upper())
                    if key not in asset_dict:
                        asset_dict[key] = {
                            "station": station,
                            "category": category,
                            "detail": detail,
                            "raw_dir": None,
                            "edited_dir": root,
                            "tim": tim
                        }
                    else:
                        prev_ed = asset_dict[key].get("edited_dir")
                        if not prev_ed or _dir_latest_mtime(root) >= _dir_latest_mtime(prev_ed):
                            asset_dict[key]["edited_dir"] = root
                            if tim:
                                asset_dict[key]["tim"] = tim

            # 3. Check jika dir_edited punya subfolder Tim_1/Tim_2 untuk asset_dict yang belum terhubung
            if os.path.isdir(dir_edited):
                for key, ainfo in asset_dict.items():
                    if not ainfo["edited_dir"]:
                        st, cat, det = ainfo["station"], ainfo["category"], ainfo["detail"]
                        for tim_name in ["Tim_1", "Tim_2", ""]:
                            cand = os.path.join(dir_edited, tim_name, st, cat, det) if tim_name else os.path.join(dir_edited, st, cat, det)
                            if os.path.isdir(cand) and any(os.path.isfile(os.path.join(cand, x)) for x in ("0.jpg", "50.jpg", "100.jpg")):
                                ainfo["edited_dir"] = cand
                                if tim_name and not ainfo["tim"]:
                                    ainfo["tim"] = tim_name.replace("_", " ").title()
                                break

            # 4. Baca daftar kolase yang telah dipotong dari cropped_collages.json atau manifest
            cropped_set = set()
            for cand_crop in [
                os.path.join(export_root, "logs", "cropped_collages.json"),
                os.path.join(export_root, "logs", "auto_crop_manifest.json"),
                os.path.join(BASE_DIR, "logs", "cropped_collages.json"),
                os.path.join(BASE_DIR, "logs", "auto_crop_manifest.json")
            ]:
                if os.path.isfile(cand_crop):
                    try:
                        with open(cand_crop, "r", encoding="utf-8") as f_c:
                            c_data = json.load(f_c)
                            if isinstance(c_data, list):
                                for x in c_data:
                                    cropped_set.add(str(x).replace("\\", "/").lower())
                            elif isinstance(c_data, dict) and "collages" in c_data:
                                for item in c_data.get("collages", []):
                                    if "rel_path" in item:
                                        cropped_set.add(str(item["rel_path"]).replace("\\", "/").lower())
                    except Exception:
                        pass

            # Bangun list aset terpadu
            assets = []
            for (st_u, cat_u, det_u), ainfo in asset_dict.items():
                station = ainfo["station"]
                category = ainfo["category"]
                detail = ainfo["detail"]
                raw_dir = ainfo["raw_dir"]
                edited_dir = ainfo["edited_dir"]
                tim = ainfo["tim"]

                norm_detail = " ".join(re.sub(r'_\d{2}-\d{2}$', '', detail.strip().upper()).split())
                matching_targets = target_files_map.get(norm_detail, [])
                matching_source = source_files_map.get(norm_detail, "")

                # Ambil tanggal: meta.json -> date.txt -> schedule_date_map
                date_text = ""
                meta_data = {}
                if edited_dir:
                    mf = os.path.join(edited_dir, "meta.json")
                    if os.path.isfile(mf):
                        try:
                            with open(mf, "r", encoding="utf-8", errors="ignore") as m_file:
                                meta_data = json.load(m_file)
                            for pk in ["0.jpg", "50.jpg", "100.jpg"]:
                                if pk in meta_data and isinstance(meta_data[pk], dict) and meta_data[pk].get("dateText"):
                                    date_text = meta_data[pk]["dateText"]
                                    break
                        except Exception:
                            pass

                if not date_text and raw_dir:
                    df = os.path.join(raw_dir, "date.txt")
                    if os.path.isfile(df):
                        try:
                            with open(df, "r", encoding="utf-8", errors="ignore") as d_file:
                                date_text = d_file.read().strip()
                        except Exception:
                            pass

                if not date_text and norm_detail in schedule_date_map:
                    date_text = schedule_date_map[norm_detail]

                rel_dir = f"{station}/{category}/{detail}"
                photos = []
                for p_name in ["0.jpg", "50.jpg", "100.jpg"]:
                    raw_path = os.path.join(raw_dir, p_name) if raw_dir else None
                    has_raw = bool(raw_path and os.path.isfile(raw_path))

                    edited_path = os.path.join(edited_dir, p_name) if edited_dir else None
                    has_edited = bool(edited_path and os.path.isfile(edited_path))

                    if not has_raw and not has_edited:
                        continue

                    # URL foto raw (HANYA jika file mentah benar-benar ada di folder 03)
                    raw_url = None
                    if has_raw:
                        mtime_r = int(os.path.getmtime(raw_path))
                        raw_url = f"/api/timemark/photo-file?path={urllib.parse.quote(os.path.abspath(raw_path))}&t={mtime_r}"

                    # URL foto edited (HANYA jika file editan benar-benar ada di folder 04)
                    edited_url = None
                    if has_edited:
                        mtime_e = int(os.path.getmtime(edited_path))
                        edited_url = f"/api/timemark/photo-file?path={urllib.parse.quote(os.path.abspath(edited_path))}&t={mtime_e}"

                    # Deteksi dan URL preview foto hasil crop kolase (03_photos_cropped_temp)
                    rel_p = f"{station}/{category}/{detail}/{p_name}".replace("\\", "/")
                    temp_photo_path = os.path.join(export_root, "03_photos_cropped_temp", station, category, detail, p_name)
                    has_temp = bool(os.path.isfile(temp_photo_path))
                    cat_u = category.upper()
                    is_cat_eligible = any(k in cat_u for k in ("CATUDAYA", "CATU DAYA", "PDSE", "PTDS", "PTLS"))
                    is_collage = bool(has_temp or (rel_p.lower() in cropped_set) or is_cat_eligible)

                    temp_url = None
                    if has_temp:
                        mtime_t = int(os.path.getmtime(temp_photo_path))
                        temp_url = f"/api/timemark/photo-file?path={urllib.parse.quote(os.path.abspath(temp_photo_path))}&t={mtime_t}"

                    p_meta = meta_data.get(p_name, {}) if isinstance(meta_data.get(p_name), dict) else {}
                    has_backup = bool(has_raw and (os.path.isfile(raw_path + ".original_backup.jpg") or os.path.isfile(raw_path + ".orig.jpg")))

                    photos.append({
                        "name": p_name,
                        "rawUrl": raw_url,
                        "editedUrl": edited_url,
                        "tempUrl": temp_url,
                        "croppedUrl": temp_url,
                        "timeUrl": None,
                        "coordUrl": None,
                        "hasRaw": has_raw,
                        "hasEdited": has_edited,
                        "hasTemp": has_temp,
                        "hasCropped": has_temp,
                        "hasTime": False,
                        "hasCoord": False,
                        "isCollage": is_collage,
                        "hasBackup": has_backup,
                        "meta": p_meta,
                        "url": edited_url if has_edited else (temp_url if has_temp else raw_url)
                    })

                has_any_edited = any(p["hasEdited"] for p in photos)
                has_any_raw = any(p["hasRaw"] for p in photos)
                has_any_collage = any(p["isCollage"] for p in photos)
                assets.append({
                    "station": station,
                    "btp": station,
                    "category": category,
                    "detail": detail,
                    "identifier": detail,
                    "relDir": rel_dir,
                    "relPath": rel_dir,
                    "dateText": date_text,
                    "targetFiles": matching_targets,
                    "sourceFile": matching_source,
                    "photos": photos,
                    "hasEdited": has_any_edited,
                    "isEdited": has_any_edited,
                    "isCollage": has_any_collage,
                    "tim": tim,
                    "sourceType": "timemark" if has_any_edited else "export"
                })

            # Sortir: Aset dengan hasEdited tampil lebih dulu, lalu yang memiliki foto mentah, lalu yang kosong
            assets.sort(key=lambda a: (0 if a["hasEdited"] else (1 if a["photos"] else 2), a["station"], a["category"], a["detail"]))

            self._json({
                "ok": True,
                "assets": assets,
                "targetFiles": sorted(target_files_list, key=lambda x: x["file"]),
                "sourceFiles": sorted(source_files_list),
                "editedCount": sum(1 for a in assets if a.get("hasEdited")),
                "exportCount": sum(1 for a in assets if not a.get("hasEdited")),
                "total": len(assets)
            })
        except Exception as e:
            _log(f"Error scanning photos: {e}")
            self._json({"ok": False, "error": str(e)}, 500)

    def _handle_timemark_photo_file(self, parsed):
        try:
            qs = urllib.parse.parse_qs(parsed.query)
            file_path = qs.get("path", [""])[0]
            if not file_path or not os.path.isfile(file_path):
                self.send_error(404, "Berkas foto tidak ditemukan")
                return
            with open(file_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-cache, max-age=0, must-revalidate")
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error(500, str(e))

    def _handle_timemark_pegawai_get(self):
        try:
            pegawai_file = os.path.join(APP_DATA_DIR, "daftar_pegawai.json")
            if not os.path.isfile(pegawai_file):
                pegawai_file = os.path.join(ENGINE_DIR, "daftar_pegawai.json")
            if not os.path.isfile(pegawai_file):
                pegawai_file = os.path.join(BASE_DIR, "config", "daftar_pegawai.json")

            presets_file = os.path.join(APP_DATA_DIR, "employee_presets.json")
            if not os.path.isfile(presets_file):
                presets_file = os.path.join(ENGINE_DIR, "employee_presets.json")
            if not os.path.isfile(presets_file):
                presets_file = os.path.join(BASE_DIR, "config", "employee_presets.json")

            daftar_pegawai = {}
            if os.path.isfile(pegawai_file):
                with open(pegawai_file, "r", encoding="utf-8") as f:
                    daftar_pegawai = json.load(f)

            presets_data = {}
            if os.path.isfile(presets_file):
                with open(presets_file, "r", encoding="utf-8") as f:
                    presets_data = json.load(f)

            active_id = presets_data.get("active_preset_id", "")
            active_name = ""
            if active_id:
                for p in presets_data.get("presets", []):
                    if p.get("id") == active_id:
                        active_name = p.get("name", "")
                        break
            if not active_name and presets_data.get("presets"):
                active_name = presets_data["presets"][0].get("name", "Standar")

            self._json({
                "ok": True,
                "daftar_pegawai": daftar_pegawai,
                "presets": presets_data.get("presets", []),
                "active_preset_id": active_id,
                "active_preset_name": active_name
            })
        except Exception as e:
            _log(f"Get pegawai error: {e}")
            self._json({"ok": False, "error": str(e)}, 500)

    def _handle_timemark_set_active_preset(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            data = json.loads(body) if body else {}
            preset_id = data.get("presetId") or data.get("active_preset_id")

            if not preset_id:
                self._json({"ok": False, "error": "Preset ID tidak diberikan."}, 400)
                return

            presets_file = os.path.join(APP_DATA_DIR, "employee_presets.json")
            if not os.path.isfile(presets_file):
                presets_file = os.path.join(ENGINE_DIR, "employee_presets.json")

            p_data = {}
            if os.path.isfile(presets_file):
                with open(presets_file, "r", encoding="utf-8") as f:
                    p_data = json.load(f)

            p_data["active_preset_id"] = preset_id
            selected_preset = next((p for p in p_data.get("presets", []) if p.get("id") == preset_id), None)

            # 1. Simpan permanen ke APP_DATA_DIR (Prioritas Utama)
            _atomic_write_json(os.path.join(APP_DATA_DIR, "employee_presets.json"), p_data)

            # Sinkronkan cadangan ke ENGINE_DIR jika memungkinkan
            try:
                _atomic_write_json(os.path.join(ENGINE_DIR, "employee_presets.json"), p_data)
            except Exception:
                pass

            if selected_preset and selected_preset.get("data"):
                _atomic_write_json(os.path.join(APP_DATA_DIR, "daftar_pegawai.json"), selected_preset["data"])
                try:
                    _atomic_write_json(os.path.join(ENGINE_DIR, "daftar_pegawai.json"), selected_preset["data"])
                except Exception:
                    pass

            _log(f"Active preset changed to: {preset_id} ({selected_preset.get('name') if selected_preset else ''})")
            self._json({
                "ok": True,
                "active_preset_id": preset_id,
                "active_preset_name": selected_preset.get("name") if selected_preset else "",
                "daftar_pegawai": selected_preset.get("data") if selected_preset else {}
            })
        except Exception as e:
            _log(f"Set active preset error: {e}")
            self._json({"ok": False, "error": str(e)}, 500)

    def _handle_timemark_pegawai_post(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            data = json.loads(body) if body else {}

            if "daftar_pegawai" in data:
                _atomic_write_json(os.path.join(APP_DATA_DIR, "daftar_pegawai.json"), data["daftar_pegawai"])
                try:
                    _atomic_write_json(os.path.join(ENGINE_DIR, "daftar_pegawai.json"), data["daftar_pegawai"])
                except Exception:
                    pass

            if "presets" in data or "active_preset_id" in data:
                presets_file = os.path.join(APP_DATA_DIR, "employee_presets.json")
                if not os.path.isfile(presets_file):
                    presets_file = os.path.join(ENGINE_DIR, "employee_presets.json")
                existing_presets = {}
                if os.path.isfile(presets_file):
                    try:
                        with open(presets_file, "r", encoding="utf-8") as f:
                            existing_presets = json.load(f)
                    except Exception:
                        pass
                if "presets" in data:
                    existing_presets["presets"] = data["presets"]
                if "active_preset_id" in data:
                    existing_presets["active_preset_id"] = data["active_preset_id"]

                _atomic_write_json(os.path.join(APP_DATA_DIR, "employee_presets.json"), existing_presets)
                try:
                    _atomic_write_json(os.path.join(ENGINE_DIR, "employee_presets.json"), existing_presets)
                except Exception:
                    pass

            self._json({"ok": True, "message": "Profil pegawai berhasil disimpan secara permanen."})
        except Exception as e:
            _log(f"Save pegawai error: {e}")
            self._json({"ok": False, "error": str(e)}, 500)

    def _handle_timemark_export_presets(self):
        try:
            presets_file = os.path.join(APP_DATA_DIR, "employee_presets.json")
            if not os.path.isfile(presets_file):
                presets_file = os.path.join(ENGINE_DIR, "employee_presets.json")

            if not os.path.isfile(presets_file):
                self._json({"ok": False, "error": "Berkas preset belum tersedia untuk diekspor."}, 404)
                return

            default_name = f"backup_preset_pegawai_{time.strftime('%Y%m%d_%H%M%S')}.json"
            chosen_path = _save_file_dialog_native(default_name)
            if not chosen_path:
                self._json({"ok": False, "cancelled": True})
                return

            shutil.copy2(presets_file, chosen_path)
            _log(f"Presets exported successfully to: {chosen_path}")
            self._json({
                "ok": True,
                "message": f"Cadangan preset berhasil disimpan ke: {os.path.basename(chosen_path)}",
                "path": chosen_path
            })
        except Exception as e:
            _log(f"Export presets error: {e}")
            self._json({"ok": False, "error": str(e)}, 500)

    def _handle_timemark_import_presets(self):
        try:
            chosen_path = _pick_json_file_native("Pilih Berkas Cadangan Preset Pegawai (*.json)")
            if not chosen_path or not os.path.isfile(chosen_path):
                self._json({"ok": False, "cancelled": True})
                return

            with open(chosen_path, "r", encoding="utf-8") as f:
                imported_data = json.load(f)

            if not isinstance(imported_data, dict):
                self._json({"ok": False, "error": "Format berkas JSON tidak valid (harus objek JSON)."}, 400)
                return

            if "presets" not in imported_data or not isinstance(imported_data["presets"], list):
                self._json({"ok": False, "error": "Berkas JSON tidak memiliki daftar 'presets' yang valid."}, 400)
                return

            # Simpan permanen ke APP_DATA_DIR
            target_file = os.path.join(APP_DATA_DIR, "employee_presets.json")
            _atomic_write_json(target_file, imported_data)

            # Sinkronkan juga active_preset ke daftar_pegawai.json
            active_id = imported_data.get("active_preset_id")
            active_preset = None
            if active_id:
                active_preset = next((p for p in imported_data["presets"] if p.get("id") == active_id), None)
            if not active_preset and imported_data["presets"]:
                active_preset = imported_data["presets"][0]
                active_id = active_preset.get("id")
                imported_data["active_preset_id"] = active_id
                _atomic_write_json(target_file, imported_data)

            if active_preset and active_preset.get("data"):
                pegawai_target = os.path.join(APP_DATA_DIR, "daftar_pegawai.json")
                _atomic_write_json(pegawai_target, active_preset["data"])

            _log(f"Presets successfully imported from: {chosen_path} ({len(imported_data.get('presets', []))} presets)")
            self._json({
                "ok": True,
                "message": f"Berhasil memulihkan {len(imported_data.get('presets', []))} preset dari {os.path.basename(chosen_path)}!",
                "presets": imported_data.get("presets", []),
                "active_preset_id": active_id,
                "active_preset_name": active_preset.get("name", "") if active_preset else ""
            })
        except json.JSONDecodeError as je:
            self._json({"ok": False, "error": f"Berkas JSON rusak atau tidak dapat dibaca: {je}"}, 400)
        except Exception as e:
            _log(f"Import presets error: {e}")
            self._json({"ok": False, "error": str(e)}, 500)

    def _handle_timemark_process_single(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            data = json.loads(body) if body else {}

            base_dir = data.get("baseExportDir") or data.get("folder") or ""
            raw_rel = data.get("rawRelPath") or data.get("assetRelPath") or ""
            photo_name = data.get("photoName") or ""
            detector = data.get("detector") or "google_vision"
            tim_group = data.get("timGroup", "Tim_1")
            custom_date = data.get("dateText", "").strip()

            if not raw_rel:
                self._json({"ok": False, "error": "Path aset (rawRelPath) wajib diberikan."}, 400)
                return

            norm_rel = raw_rel.replace("\\", "/").strip("/")
            parts = norm_rel.split("/")
            if norm_rel.lower().endswith(".jpg"):
                asset_rel = "/".join(parts[:-1])
                target_fnames = [parts[-1]]
            else:
                asset_rel = norm_rel
                if photo_name and photo_name.lower().endswith(".jpg"):
                    target_fnames = [photo_name]
                else:
                    target_fnames = ["0.jpg", "50.jpg", "100.jpg"]

            export_root, photos_export, photos_edited = _resolve_photo_directories(base_dir)
            os.makedirs(photos_edited, exist_ok=True)

            schedule_file = os.path.join(export_root, "schedule.json")
            if not os.path.isfile(schedule_file):
                cand_sched = os.path.join(os.path.dirname(export_root), "schedule.json")
                if os.path.isfile(cand_sched):
                    schedule_file = cand_sched

            # Cari tanggal dari date.txt jika custom_date tidak diberikan
            date_to_use = custom_date
            if not date_to_use:
                df = os.path.join(photos_export, asset_rel, "date.txt")
                if os.path.isfile(df):
                    try:
                        with open(df, "r", encoding="utf-8", errors="ignore") as f:
                            date_to_use = f.read().strip()
                    except Exception:
                        pass

            def calc_photo_date(base_dt, stem):
                clean_dt = str(base_dt or "").strip()
                m = re.search(r"^(.*?\d{4})\s+(\d{2}):(\d{2})$", clean_dt)
                if not m:
                    return clean_dt
                d_part, hh, mm = m.group(1), int(m.group(2)), int(m.group(3))
                tot = hh * 60 + mm
                pct = 50 if stem == "50" else (100 if stem == "100" else 0)
                tot += round((pct * 45) / 100)
                return f"{d_part} {(tot // 60) % 24:02d}:{tot % 60:02d}"

            sub_env = os.environ.copy()
            sub_env["PYTHONUNBUFFERED"] = "1"
            sub_env["PYTHONIOENCODING"] = "utf-8"

            processed = 0
            meta_saved = {}
            for fname in target_fnames:
                stem = os.path.splitext(fname)[0]
                p_date = calc_photo_date(date_to_use, stem) if date_to_use else ""

                # Prioritaskan foto hasil potong kolase (03_photos_cropped_temp) jika ada
                temp_cand = os.path.join(export_root, "03_photos_cropped_temp", asset_rel, fname)
                in_cand = os.path.join(photos_export, asset_rel, fname)
                if os.path.isfile(temp_cand):
                    in_cand = temp_cand
                elif not os.path.isfile(in_cand):
                    in_cand = os.path.join(photos_edited, tim_group, asset_rel, fname)
                    if not os.path.isfile(in_cand):
                        continue

                out_target = os.path.join(photos_edited, tim_group, asset_rel, fname)
                os.makedirs(os.path.dirname(out_target), exist_ok=True)

                args = [
                    "--input", in_cand,
                    "--single-out", out_target,
                    "--detector", detector
                ]
                if p_date:
                    args.extend(["--date", p_date])
                elif os.path.isfile(schedule_file):
                    args.extend(["--schedule", schedule_file])

                cmd = make_script_cmd("edit_timemark_ide1.py", args)
                proc = subprocess.run(
                    cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=sub_env, cwd=BASE_DIR,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
                )

                if os.path.isfile(out_target):
                    processed += 1
                    # Sinkronkan ke folder Tim lain jika aset ini memiliki duplikat di Tim_1/Tim_2/Tim_3/root
                    for alt_t in ["", "Tim_1", "Tim_2", "Tim_3", "Tim_4"]:
                        ao = os.path.join(photos_edited, alt_t, asset_rel, fname) if alt_t else os.path.join(photos_edited, asset_rel, fname)
                        if os.path.abspath(ao) != os.path.abspath(out_target) and os.path.isfile(ao):
                            try:
                                shutil.copy2(out_target, ao)
                            except Exception:
                                pass
                    meta_saved[fname] = {
                        "dateText": p_date,
                        "detector": detector,
                        "timestamp": time.time()
                    }

            if meta_saved:
                meta_dirs = {os.path.join(photos_edited, tim_group, asset_rel)}
                for alt_t in ["", "Tim_1", "Tim_2", "Tim_3", "Tim_4"]:
                    ad = os.path.join(photos_edited, alt_t, asset_rel) if alt_t else os.path.join(photos_edited, asset_rel)
                    if os.path.isdir(ad):
                        meta_dirs.add(ad)
                for target_meta_dir in meta_dirs:
                    meta_file = os.path.join(target_meta_dir, "meta.json")
                    curr_meta = {}
                    if os.path.isfile(meta_file):
                        try:
                            with open(meta_file, "r", encoding="utf-8") as mf:
                                curr_meta = json.load(mf)
                        except Exception:
                            pass
                    curr_meta.update(meta_saved)
                    try:
                        with open(meta_file, "w", encoding="utf-8") as mf:
                            json.dump(curr_meta, mf, indent=2, ensure_ascii=False)
                    except Exception:
                        pass

            if processed > 0:
                detector_title = "Google AI Vision" if detector == "google_vision" else "Metode Biasa (HSV)"
                self._json({
                    "ok": True,
                    "success": True,
                    "processed": processed,
                    "detector": detector,
                    "message": f"Berhasil memproses timemark untuk {processed} foto menggunakan {detector_title}!"
                })
            else:
                self._json({
                    "ok": False,
                    "error": "Tidak ada foto mentah yang ditemukan untuk diproses di folder aset tersebut."
                }, 404)
        except Exception as e:
            _log(f"Single timemark error: {e}")
            self._json({"ok": False, "error": str(e)}, 500)

    def _handle_timemark_manual_edit(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            data = json.loads(body) if body else {}

            base_dir = data.get("baseExportDir") or data.get("folder") or ""
            raw_rel = data.get("rawRelPath") or data.get("assetRelPath") or ""
            date_text = data.get("dateText", "").strip()
            y_pos = data.get("yPos")
            x_pos = data.get("xPos")
            apply_to_folder = data.get("applyToFolder", True)
            tim_group = data.get("timGroup", "Tim_1")
            detector = data.get("detector") or "google_vision"

            if not raw_rel:
                self._json({"ok": False, "error": "rawRelPath wajib diisi."}, 400)
                return

            norm_rel = raw_rel.replace("\\", "/").strip("/")
            parts = norm_rel.split("/")
            origin_stem = "0"
            if norm_rel.lower().endswith(".jpg"):
                asset_rel = "/".join(parts[:-1])
                curr_fname = parts[-1]
                origin_stem = os.path.splitext(curr_fname)[0]
                target_fnames = [curr_fname] if not apply_to_folder else ["0.jpg", "50.jpg", "100.jpg"]
            else:
                asset_rel = norm_rel
                target_fnames = ["0.jpg", "50.jpg", "100.jpg"]

            export_root, photos_export, photos_edited = _resolve_photo_directories(base_dir)
            os.makedirs(photos_edited, exist_ok=True)

            # Jika date_text kosong, coba baca dari date.txt atau meta.json
            if not date_text:
                for cand_date_file in [
                    os.path.join(photos_export, asset_rel, "date.txt"),
                    os.path.join(photos_edited, asset_rel, "date.txt"),
                    os.path.join(photos_edited, tim_group, asset_rel, "date.txt")
                ]:
                    if os.path.isfile(cand_date_file):
                        try:
                            with open(cand_date_file, "r", encoding="utf-8", errors="ignore") as df:
                                date_text = df.read().strip()
                            if date_text:
                                break
                        except Exception:
                            pass

            def calc_photo_date(base_dt, stem):
                clean_dt = str(base_dt or "").strip()
                m = re.search(r"^(.*?\d{4})\s+(\d{2}):(\d{2})$", clean_dt)
                if not m:
                    return clean_dt
                d_part, hh, mm = m.group(1), int(m.group(2)), int(m.group(3))
                tot = hh * 60 + mm

                # Jika base_dt berasal dari foto 50%, normalisasikan dulu ke 0% (kurangi 23 menit)
                if origin_stem == "50":
                    tot -= round((50 * 45) / 100)
                elif origin_stem == "100":
                    tot -= round((100 * 45) / 100)

                pct = 50 if stem == "50" else (100 if stem == "100" else 0)
                tot += round((pct * 45) / 100)
                if tot < 0:
                    tot += 24 * 60
                return f"{d_part} {(tot // 60) % 24:02d}:{tot % 60:02d}"

            sub_env = os.environ.copy()
            sub_env["PYTHONUNBUFFERED"] = "1"
            sub_env["PYTHONIOENCODING"] = "utf-8"

            meta_saved = {}
            for fname in target_fnames:
                stem = os.path.splitext(fname)[0]
                if not apply_to_folder:
                    # Edit tunggal foto ini saja (misal khusus foto kedua 50.jpg): gunakan date_text langsung
                    p_date = date_text
                else:
                    p_date = calc_photo_date(date_text, stem)

                # 1. Cari file input mentah
                in_cand = None
                for cand in [
                    os.path.join(photos_export, asset_rel, fname),
                    os.path.join(photos_export, "Tim_1", asset_rel, fname),
                    os.path.join(photos_export, "Tim_2", asset_rel, fname)
                ]:
                    if os.path.isfile(cand):
                        in_cand = cand
                        break

                # 2. Tentukan target output di photos_edited (prioritaskan folder yang sudah ada)
                out_target = None
                for cand_out in [
                    os.path.join(photos_edited, asset_rel, fname),
                    os.path.join(photos_edited, tim_group, asset_rel, fname),
                    os.path.join(photos_edited, "Tim_1", asset_rel, fname),
                    os.path.join(photos_edited, "Tim_2", asset_rel, fname)
                ]:
                    if os.path.isfile(cand_out):
                        out_target = cand_out
                        break

                if not out_target:
                    if os.path.isdir(os.path.join(photos_edited, tim_group)):
                        out_target = os.path.join(photos_edited, tim_group, asset_rel, fname)
                    else:
                        out_target = os.path.join(photos_edited, asset_rel, fname)

                # Jika in_cand belum ketemu, gunakan foto yang sudah ada
                if not in_cand:
                    if out_target and os.path.isfile(out_target):
                        in_cand = out_target
                    else:
                        continue

                os.makedirs(os.path.dirname(out_target), exist_ok=True)

                cmd = make_script_cmd("edit_timemark_ide1.py", [
                    "--input", in_cand,
                    "--single-out", out_target,
                    "--detector", detector
                ])
                if p_date:
                    cmd.extend(["--date", p_date])
                if y_pos is not None and str(y_pos) != "":
                    cmd.extend(["--y-override", str(y_pos)])
                if x_pos is not None and str(x_pos) != "":
                    cmd.extend(["--x-override", str(x_pos)])

                subprocess.run(
                    cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=sub_env, cwd=BASE_DIR,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
                )

                # Jika ada duplikasi di path tanpa Tim_1 atau dengan Tim_1, sinkronkan
                alt_outs = [
                    os.path.join(photos_edited, asset_rel, fname),
                    os.path.join(photos_edited, "Tim_1", asset_rel, fname),
                    os.path.join(photos_edited, "Tim_2", asset_rel, fname)
                ]
                for ao in alt_outs:
                    if ao != out_target and os.path.isfile(ao):
                        try:
                            shutil.copy2(out_target, ao)
                        except Exception:
                            pass

                meta_saved[fname] = {
                    "dateText": p_date,
                    "yPos": int(y_pos) if (y_pos is not None and str(y_pos) != "") else 220,
                    "xPos": int(x_pos) if (x_pos is not None and str(x_pos) != "") else 14,
                    "manualEdit": True,
                    "detector": detector,
                    "timestamp": time.time()
                }

            if meta_saved:
                # Simpan meta.json di folder output
                meta_dirs = {os.path.dirname(out_target)}
                for ao in alt_outs:
                    if os.path.isfile(ao):
                        meta_dirs.add(os.path.dirname(ao))

                for target_meta_dir in meta_dirs:
                    meta_file = os.path.join(target_meta_dir, "meta.json")
                    curr_meta = {}
                    if os.path.isfile(meta_file):
                        try:
                            with open(meta_file, "r", encoding="utf-8") as mf:
                                curr_meta = json.load(mf)
                        except Exception:
                            pass
                    curr_meta.update(meta_saved)
                    try:
                        with open(meta_file, "w", encoding="utf-8") as mf:
                            json.dump(curr_meta, mf, indent=2, ensure_ascii=False)
                    except Exception:
                        pass

                if date_text:
                    for d_dir in [os.path.join(photos_export, asset_rel), os.path.dirname(out_target)]:
                        try:
                            os.makedirs(d_dir, exist_ok=True)
                            with open(os.path.join(d_dir, "date.txt"), "w", encoding="utf-8") as df:
                                df.write(date_text + "\n")
                        except Exception:
                            pass

            self._json({"ok": True, "success": True, "message": "Timemark berhasil diperbarui dan disimpan."})
        except Exception as e:
            _log(f"Manual edit error: {e}")
            self._json({"ok": False, "error": str(e)}, 500)

    def _handle_timemark_swap_photo(self):
        """
        Menukar posisi fisik berkas foto mentah (03_export_foto) dan mereproses watermark (04_photos_edited).
        Sangat berguna jika urutan foto terbalik (misal Foto 50% / foto kedua tertukar dengan Foto 0% / foto pertama).
        """
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            data = json.loads(body) if body else {}

            base_dir = data.get("baseExportDir") or data.get("folder") or ""
            source_rel = data.get("sourceRel") or ""
            target_rel = data.get("targetRel") or ""
            detector = data.get("detector") or "google_vision"

            if not source_rel or not target_rel:
                self._json({"ok": False, "error": "sourceRel dan targetRel wajib diisi."}, 400)
                return

            if source_rel == target_rel:
                self._json({"ok": True, "message": "Foto sumber dan tujuan sama."})
                return

            export_root, photos_export, photos_edited = _resolve_photo_directories(base_dir or BASE_DIR)

            norm_src = source_rel.replace("\\", "/").strip("/")
            norm_tgt = target_rel.replace("\\", "/").strip("/")

            src_file = os.path.normpath(os.path.join(photos_export, norm_src))
            tgt_file = os.path.normpath(os.path.join(photos_export, norm_tgt))

            # Jika path tidak langsung ketemu di photos_export, lakukan pencarian toleran
            if not os.path.isfile(src_file) or not os.path.isfile(tgt_file):
                for r, d, fls in os.walk(photos_export):
                    if not os.path.isfile(src_file) and os.path.basename(norm_src) in fls:
                        c = os.path.join(r, os.path.basename(norm_src))
                        if os.path.normpath(c).lower().endswith(os.path.normpath(norm_src).lower()):
                            src_file = c
                    if not os.path.isfile(tgt_file) and os.path.basename(norm_tgt) in fls:
                        c = os.path.join(r, os.path.basename(norm_tgt))
                        if os.path.normpath(c).lower().endswith(os.path.normpath(norm_tgt).lower()):
                            tgt_file = c

            if not os.path.isfile(src_file):
                self._json({"ok": False, "error": f"Foto sumber tidak ditemukan: {norm_src}"}, 404)
                return
            if not os.path.isfile(tgt_file):
                self._json({"ok": False, "error": f"Foto target tidak ditemukan: {norm_tgt}"}, 404)
                return

            # Simpan backup kedua file mentah jika belum pernah dibackup
            for p in [src_file, tgt_file]:
                b_path = p + ".original_backup.jpg"
                if not os.path.isfile(b_path):
                    try:
                        shutil.copy2(p, b_path)
                    except Exception:
                        pass

            # Swap file fisik mentah
            tmp_swap = tgt_file + f".swap_tmp_{os.getpid()}.jpg"
            shutil.move(src_file, tmp_swap)
            shutil.move(tgt_file, src_file)
            shutil.move(tmp_swap, tgt_file)

            # Reproses kedua foto di 04_photos_edited
            sub_env = os.environ.copy()
            sub_env["PYTHONUNBUFFERED"] = "1"
            sub_env["PYTHONIOENCODING"] = "utf-8"

            for file_p, rel_p in [(src_file, norm_src), (tgt_file, norm_tgt)]:
                # Ambil date.txt jika ada
                p_dir = os.path.dirname(file_p)
                d_file = os.path.join(p_dir, "date.txt")
                d_text = ""
                if os.path.isfile(d_file):
                    try:
                        with open(d_file, "r", encoding="utf-8") as df:
                            d_text = df.read().strip()
                    except Exception:
                        pass

                stem = os.path.splitext(os.path.basename(file_p))[0]
                p_date = ""
                if d_text:
                    m = re.search(r"^(.*?\d{4})\s+(\d{2}):(\d{2})$", d_text)
                    if m:
                        d_part, hh, mm = m.group(1), int(m.group(2)), int(m.group(3))
                        tot = hh * 60 + mm
                        pct = 50 if stem == "50" else (100 if stem == "100" else 0)
                        tot += round((pct * 45) / 100)
                        p_date = f"{d_part} {(tot // 60) % 24:02d}:{tot % 60:02d}"

                out_target = None
                for cand_out in [
                    os.path.join(photos_edited, rel_p),
                    os.path.join(photos_edited, "Tim_1", rel_p),
                    os.path.join(photos_edited, "Tim_2", rel_p)
                ]:
                    if os.path.isfile(cand_out):
                        out_target = cand_out
                        break
                if not out_target:
                    out_target = os.path.join(photos_edited, rel_p)

                os.makedirs(os.path.dirname(out_target), exist_ok=True)
                cmd = make_script_cmd("edit_timemark_ide1.py", [
                    "--input", file_p,
                    "--single-out", out_target,
                    "--detector", detector
                ])
                if p_date:
                    cmd.extend(["--date", p_date])

                subprocess.run(
                    cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=sub_env, cwd=BASE_DIR,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
                )

            self._json({
                "ok": True,
                "success": True,
                "message": f"Berhasil menukar posisi foto {os.path.basename(norm_src)} dengan {os.path.basename(norm_tgt)}."
            })
        except Exception as e:
            self._json({"ok": False, "error": str(e)}, 500)

    def _handle_timemark_crop_collage_single(self):
        try:
            from pathlib import Path
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            data = json.loads(body) if body else {}

            base_dir = data.get("baseExportDir") or data.get("folder") or ""
            rel = (data.get("rel") or "").replace("\\", "/").strip("/")
            detector = data.get("detector") or "google_vision"

            if not rel:
                self._json({"ok": False, "error": "Parameter rel wajib diisi."}, 400)
                return

            export_root, photos_export, photos_edited = _resolve_photo_directories(base_dir or BASE_DIR)
            src_path = Path(photos_export) / rel
            if not src_path.is_file():
                self._json({"ok": False, "error": f"Foto mentah tidak ditemukan: {src_path}"}, 404)
                return

            temp_dst = Path(export_root) / "03_photos_cropped_temp" / rel
            set_file = Path(export_root) / "logs" / "cropped_collages.json"
            asset_rel = os.path.dirname(rel).replace("\\", "/")
            fname = os.path.basename(rel)
            stem = os.path.splitext(fname)[0]

            # Cek kuadran terakhir dari meta.json jika sudah pernah di-crop
            prev_quad = None
            for tim_cand in ["Tim_1", "Tim_2", "Tim_3", "Tim_4", ""]:
                mf_cand = os.path.join(photos_edited, tim_cand, asset_rel, "meta.json") if tim_cand else os.path.join(photos_edited, asset_rel, "meta.json")
                if os.path.isfile(mf_cand):
                    try:
                        with open(mf_cand, "r", encoding="utf-8") as mf:
                            mdata = json.load(mf)
                        if isinstance(mdata.get(fname), dict) and mdata[fname].get("cropQuadrant"):
                            prev_quad = str(mdata[fname]["cropQuadrant"]).upper()
                            break
                    except Exception:
                        pass

            req_quad = (data.get("quadrant") or "").strip().upper()
            if not req_quad and temp_dst.is_file():
                # Jika user klik "Potong Ulang" tanpa parameter kuadran, putar siklus kuadran:
                # TL (Kiri-Atas) -> TR (Kanan-Atas) -> BL (Kiri-Bawah) -> BR (Kanan-Bawah) -> ORIGINAL (Utuh)
                cycle_order = ["TL", "TR", "BL", "BR", "ORIGINAL"]
                if prev_quad in cycle_order:
                    next_idx = (cycle_order.index(prev_quad) + 1) % len(cycle_order)
                    req_quad = cycle_order[next_idx]
                else:
                    req_quad = "TL"

            quad_labels = {
                "TL": "Kiri-Atas (TL)",
                "TR": "Kanan-Atas (TR)",
                "BL": "Kiri-Bawah (BL)",
                "BR": "Kanan-Bawah (BR)",
                "TOP_PANEL": "Panel Atas (3-in-1)",
                "ORIGINAL": "Utuh (Tanpa Crop)"
            }

            # Mode ORIGINAL / UNCROP: Hapus hasil crop dan kembalikan ke foto utuh (03_export_foto)
            is_uncrop = req_quad in ("ORIGINAL", "NONE", "UNCROP", "FULL")
            if is_uncrop:
                if temp_dst.is_file():
                    try:
                        temp_dst.unlink()
                    except Exception:
                        pass
                if set_file.is_file():
                    try:
                        crops_list = json.loads(set_file.read_text(encoding="utf-8"))
                        crops_list = [x for x in crops_list if x.lower() != rel.lower()]
                        set_file.write_text(json.dumps(sorted(crops_list), indent=2, ensure_ascii=False), encoding="utf-8")
                    except Exception:
                        pass
                input_for_timemark = src_path
                layout = "single_photo"
                crop_box = None
                stats = {"chosen_quadrant": "ORIGINAL"}
            else:
                # Import helper deteksi & crop kolase
                sys.path.insert(0, os.path.join(APP_DIR, "timemark_engine"))
                from auto_crop_collages import detect_white_seam_collage
                from PIL import Image

                layout, crop_box, stats = detect_white_seam_collage(src_path, requested_quadrant=req_quad or None)

                img = Image.open(src_path).convert("RGB")
                w, h = img.size

                # Jika user meminta potong manual pada foto yang garis putihnya tipis, gunakan kuadran 2x2 standar (default TL)
                if layout == "single_photo" or not crop_box:
                    layout = "2x2"
                    quads = {
                        "TL": (0, 0, w // 2, h // 2),
                        "TR": (w // 2, 0, w, h // 2),
                        "BL": (0, h // 2, w // 2, h),
                        "BR": (w // 2, h // 2, w, h)
                    }
                    chosen = req_quad if req_quad in quads else "TL"
                    crop_box = quads[chosen]
                    stats = stats or {}
                    stats["chosen_quadrant"] = chosen
                    stats["fallback"] = True

                x1, y1, x2, y2 = crop_box
                cropped_img = img.crop((x1, y1, x2, y2))
                resized_img = cropped_img.resize((300, 300), Image.Resampling.LANCZOS)

                temp_dst.parent.mkdir(parents=True, exist_ok=True)
                resized_img.save(temp_dst, quality=95, subsampling=0)

                # Update cropped_collages.json
                set_file.parent.mkdir(parents=True, exist_ok=True)
                crops_list = []
                if set_file.is_file():
                    try:
                        crops_list = json.loads(set_file.read_text(encoding="utf-8"))
                    except Exception:
                        crops_list = []
                if rel.lower() not in [x.lower() for x in crops_list]:
                    crops_list.append(rel)
                    set_file.write_text(json.dumps(sorted(crops_list), indent=2, ensure_ascii=False), encoding="utf-8")

                input_for_timemark = temp_dst

            # Sinkronisasi otomatis: Re-proses timemark di 04_photos_edited
            date_to_use = ""
            for cand_date in [
                os.path.join(photos_export, asset_rel, "date.txt"),
                os.path.join(photos_edited, asset_rel, "date.txt"),
                os.path.join(photos_edited, "Tim_1", asset_rel, "date.txt"),
                os.path.join(photos_edited, "Tim_2", asset_rel, "date.txt"),
                os.path.join(photos_edited, "Tim_3", asset_rel, "date.txt"),
            ]:
                if os.path.isfile(cand_date):
                    try:
                        with open(cand_date, "r", encoding="utf-8", errors="ignore") as df:
                            date_to_use = df.read().strip()
                        if date_to_use:
                            break
                    except Exception:
                        pass

            def calc_photo_date(base_dt, stem):
                clean_dt = str(base_dt or "").strip()
                m = re.search(r"^(.*?\d{4})\s+(\d{2}):(\d{2})$", clean_dt)
                if not m:
                    return clean_dt
                d_part, hh, mm = m.group(1), int(m.group(2)), int(m.group(3))
                tot = hh * 60 + mm
                pct = 50 if stem == "50" else (100 if stem == "100" else 0)
                tot += round((pct * 45) / 100)
                return f"{d_part} {(tot // 60) % 24:02d}:{tot % 60:02d}"

            p_date = calc_photo_date(date_to_use, stem) if date_to_use else ""

            sub_env = os.environ.copy()
            sub_env["PYTHONUNBUFFERED"] = "1"
            sub_env["PYTHONIOENCODING"] = "utf-8"

            # Cari semua target folder aset yang sudah ada di 04_photos_edited (Tim_1/Tim_2/Tim_3/Tim_4/root)
            existing_targets = []
            for tim_group in ["Tim_1", "Tim_2", "Tim_3", "Tim_4", ""]:
                t_folder = os.path.join(photos_edited, tim_group) if tim_group else photos_edited
                asset_folder = os.path.join(t_folder, asset_rel)
                if os.path.isdir(asset_folder):
                    existing_targets.append(os.path.join(asset_folder, fname))
            if not existing_targets:
                existing_targets.append(os.path.join(photos_edited, "Tim_1", asset_rel, fname))

            primary_out = existing_targets[0]
            os.makedirs(os.path.dirname(primary_out), exist_ok=True)
            args = [
                "--input", str(input_for_timemark),
                "--single-out", primary_out,
                "--detector", detector
            ]
            if p_date:
                args.extend(["--date", p_date])
            cmd = make_script_cmd("edit_timemark_ide1.py", args)
            try:
                subprocess.run(
                    cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                    env=sub_env, cwd=BASE_DIR, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
                )
            except Exception as err:
                _log(f"Auto re-timemark after crop failed: {err}")

            if os.path.isfile(primary_out):
                for extra_out in existing_targets[1:]:
                    try:
                        os.makedirs(os.path.dirname(extra_out), exist_ok=True)
                        shutil.copy2(primary_out, extra_out)
                    except Exception:
                        pass

            chosen_q = stats.get("chosen_quadrant", "TL")
            for target_out in existing_targets:
                meta_file = os.path.join(os.path.dirname(target_out), "meta.json")
                curr_meta = {}
                if os.path.isfile(meta_file):
                    try:
                        with open(meta_file, "r", encoding="utf-8") as mf:
                            curr_meta = json.load(mf)
                    except Exception:
                        pass
                f_entry = curr_meta.get(fname, {}) if isinstance(curr_meta.get(fname), dict) else {}
                if is_uncrop:
                    f_entry.pop("cropQuadrant", None)
                else:
                    f_entry["cropQuadrant"] = chosen_q
                if p_date:
                    f_entry["dateText"] = p_date
                f_entry["timestamp"] = time.time()
                curr_meta[fname] = f_entry
                try:
                    with open(meta_file, "w", encoding="utf-8") as mf:
                        json.dump(curr_meta, mf, indent=2, ensure_ascii=False)
                except Exception:
                    pass

            temp_url = None
            if not is_uncrop and temp_dst.is_file():
                mtime_t = int(os.path.getmtime(temp_dst))
                temp_url = f"/api/timemark/photo-file?path={urllib.parse.quote(os.path.abspath(temp_dst))}&t={mtime_t}"

            q_label = quad_labels.get(chosen_q, chosen_q)
            msg = (
                f"Foto dikembalikan ke ukuran utuh (Tanpa Crop) dan timemark diperbarui!"
                if is_uncrop
                else f"Kolase dipotong ke kuadran {q_label} dan timemark diperbarui!"
            )

            self._json({
                "ok": True,
                "message": msg,
                "tempUrl": temp_url,
                "uncropped": is_uncrop,
                "quadrant": chosen_q,
                "layout": layout,
                "cropBox": crop_box,
                "stats": stats
            })
        except Exception as e:
            _log(f"Crop collage single error: {e}")
            self._json({"ok": False, "error": str(e)}, 500)


    def _handle_timemark_remerge_single(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            data = json.loads(body) if body else {}

            raw_rel = data.get("rawRelPath", "")
            pdf_name = data.get("pdfName") or data.get("targetPdfName") or ""
            base_dir = data.get("baseExportDir") or data.get("folder") or ""
            target_dir = data.get("targetDir") or ""
            merged_dir = data.get("mergedDir") or ""

            export_root, _, photos_edited = _resolve_photo_directories(base_dir)

            if not target_dir or not os.path.isdir(target_dir):
                cand_targets = [
                    os.path.join(export_root, "02_pdf_target"),
                    os.path.join(os.path.dirname(export_root), "02_pdf_target"),
                    os.path.join(BASE_DIR, "02_pdf_target"),
                ]
                for ct in cand_targets:
                    if os.path.isdir(ct):
                        target_dir = ct
                        break

            if not merged_dir:
                merged_dir = os.path.join(export_root, "05_pdf_merged")
            os.makedirs(merged_dir, exist_ok=True)

            if not pdf_name and raw_rel:
                norm_rel = raw_rel.replace("\\", "/").strip("/")
                parts = norm_rel.split("/")
                ident = parts[-2] if len(parts) >= 2 and parts[-1].lower().endswith(".jpg") else parts[-1]
                norm_ident = " ".join(re.sub(r'_\d{2}-\d{2}$', '', ident.strip().upper()).split())

                sched_path = os.path.join(export_root, "schedule.json")
                if os.path.isfile(sched_path):
                    try:
                        with open(sched_path, "r", encoding="utf-8") as sf:
                            sched = json.load(sf)
                        for item in sched.get("schedules", []):
                            i_id = " ".join(re.sub(r'_\d{2}-\d{2}$', '', (item.get("identifier") or "").strip().upper()).split())
                            b_id = " ".join(re.sub(r'_\d{2}-\d{2}$', '', (item.get("base_identifier") or "").strip().upper()).split())
                            if norm_ident == i_id or norm_ident == b_id:
                                pdf_name = item.get("file")
                                break
                    except Exception:
                        pass

                if not pdf_name and target_dir and os.path.isdir(target_dir):
                    for fn in os.listdir(target_dir):
                        if fn.lower().endswith(".pdf") and norm_ident in fn.upper():
                            pdf_name = fn
                            break

            if not pdf_name:
                self._json({"ok": False, "error": "Nama berkas PDF target tidak dapat ditemukan."}, 400)
                return

            target_file_full = os.path.join(target_dir, pdf_name) if target_dir else ""
            if not target_file_full or not os.path.isfile(target_file_full):
                self._json({"ok": False, "error": f"Berkas target tidak ditemukan di folder target: {pdf_name}"}, 404)
                return

            sub_env = os.environ.copy()
            sub_env["PYTHONUNBUFFERED"] = "1"
            sub_env["PYTHONIOENCODING"] = "utf-8"

            cmd = make_script_cmd("merge_pdf_foto.py", [
                "--input", target_dir,
                "--photos", photos_edited,
                "--output", merged_dir,
                "--file", pdf_name
            ])

            res = subprocess.run(
                cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=sub_env, cwd=BASE_DIR,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            )

            out_file_path = ""
            for r, d, files in os.walk(merged_dir):
                if pdf_name in files:
                    out_file_path = os.path.join(r, pdf_name)
                    break

            file_url = f"/api/timemark/photo-file?path={urllib.parse.quote(os.path.abspath(out_file_path))}" if out_file_path else ""

            self._json({
                "ok": True,
                "success": True,
                "status": "ok",
                "pdfName": pdf_name,
                "outputPath": out_file_path,
                "fileUrl": file_url,
                "details": res.stdout[-400:] if res.stdout else ""
            })
        except Exception as e:
            _log(f"Remerge single error: {e}")
            self._json({"ok": False, "error": str(e)}, 500)

    def _handle_timemark_revert_photo(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            data = json.loads(body) if body else {}

            base_dir = data.get("baseExportDir") or data.get("folder") or ""
            raw_rel = data.get("rawRelPath") or data.get("assetRelPath") or data.get("rel") or ""
            photo_name = data.get("photoName") or "0.jpg"

            norm_rel = raw_rel.replace("\\", "/").strip("/")
            parts = norm_rel.split("/")
            if norm_rel.lower().endswith(".jpg"):
                asset_rel = "/".join(parts[:-1])
                photo_name = parts[-1]
            else:
                asset_rel = norm_rel

            export_root, photos_export, photos_edited = _resolve_photo_directories(base_dir or BASE_DIR)

            target_photo = os.path.normpath(os.path.join(photos_export, asset_rel, photo_name))
            backup_file = target_photo + ".original_backup.jpg"
            if not os.path.isfile(backup_file):
                backup_file = target_photo + ".orig.jpg"

            if not os.path.isfile(backup_file):
                self._json({"ok": False, "error": "Salinan foto asli tidak ditemukan untuk dipulihkan."}, 404)
                return

            shutil.copy2(backup_file, target_photo)
            try:
                os.remove(backup_file)
            except Exception:
                pass

            date_file = os.path.join(photos_export, asset_rel, "date.txt")
            date_text = ""
            if os.path.isfile(date_file):
                with open(date_file, "r", encoding="utf-8") as df:
                    date_text = df.read().strip()

            out_target = os.path.join(photos_edited, "Tim_1", asset_rel, photo_name)
            if date_text and os.path.isdir(photos_edited):
                sub_env = os.environ.copy()
                sub_env["PYTHONUNBUFFERED"] = "1"
                cmd = make_script_cmd("edit_timemark_ide1.py", [
                    "--input", target_photo,
                    "--single-out", out_target,
                    "--date", date_text,
                    "--detector", "guide"
                ])
                subprocess.run(cmd, capture_output=True, text=True, env=sub_env, cwd=BASE_DIR, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000))

            self._json({"ok": True, "success": True, "message": "Foto berhasil dipulihkan ke versi asli."})
        except Exception as e:
            _log(f"Revert photo error: {e}")
            self._json({"ok": False, "error": str(e)}, 500)

    def _handle_timemark_edit_time(self):
        self._handle_timemark_manual_edit()

    def _handle_timemark_edit_coord(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            data = json.loads(body) if body else {}
            base_dir = data.get("baseExportDir", "")
            rel_path = data.get("assetRelPath", "")
            photo_name = data.get("photoName", "0.jpg")
            y_override = int(data.get("yOverride", 195))

            target_photo = os.path.normpath(os.path.join(base_dir, rel_path, photo_name))
            if not os.path.isfile(target_photo):
                self._json({"ok": False, "error": "Berkas foto tidak ditemukan."}, 404)
                return

            sub_env = os.environ.copy()
            sub_env["PYTHONUNBUFFERED"] = "1"
            sub_env["PYTHONIOENCODING"] = "utf-8"

            cmd = make_script_cmd("edit_timemark_ide1.py", [
                "--input", target_photo,
                "--y-override", str(y_override),
                "--detector", "guide"
            ])
            subprocess.run(
                cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=sub_env, cwd=BASE_DIR,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            )
            self._json({"ok": True, "message": f"Koordinat y={y_override} berhasil diterapkan."})
        except Exception as e:
            _log(f"Edit coord error: {e}")
            self._json({"ok": False, "error": str(e)}, 500)

    def _handle_timemark_replace_photo(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            data = json.loads(body) if body else {}
            base_dir = data.get("baseExportDir", "")
            rel_path = data.get("assetRelPath", "") or data.get("rel", "")
            photo_name = data.get("photoName", "")
            img_b64 = data.get("imageBase64", "")

            if not img_b64:
                self._json({"ok": False, "error": "Data gambar kosong."}, 400)
                return

            norm_rel = rel_path.replace("\\", "/").strip("/")
            parts = norm_rel.split("/")
            if norm_rel.lower().endswith(".jpg"):
                asset_rel = "/".join(parts[:-1])
                photo_name = parts[-1]
            else:
                asset_rel = norm_rel
                if not photo_name:
                    photo_name = "0.jpg"

            export_root, photos_export, photos_edited = _resolve_photo_directories(base_dir or BASE_DIR)

            target_photo = os.path.normpath(os.path.join(photos_export, asset_rel, photo_name))
            if not os.path.isfile(target_photo):
                os.makedirs(os.path.dirname(target_photo), exist_ok=True)

            backup_file = target_photo + ".original_backup.jpg"
            if os.path.isfile(target_photo) and not os.path.isfile(backup_file):
                shutil.copy2(target_photo, backup_file)

            raw_bytes = base64.b64decode(img_b64)
            with open(target_photo, "wb") as pf:
                pf.write(raw_bytes)

            out_target = os.path.join(photos_edited, "Tim_1", asset_rel, photo_name)
            os.makedirs(os.path.dirname(out_target), exist_ok=True)

            date_file = os.path.join(photos_export, asset_rel, "date.txt")
            date_text = ""
            if os.path.isfile(date_file):
                with open(date_file, "r", encoding="utf-8") as df:
                    date_text = df.read().strip()

            sub_env = os.environ.copy()
            sub_env["PYTHONUNBUFFERED"] = "1"
            sub_env["PYTHONIOENCODING"] = "utf-8"

            cmd = make_script_cmd("edit_timemark_ide1.py", [
                "--input", target_photo,
                "--single-out", out_target,
                "--detector", "guide"
            ])
            if date_text:
                cmd.extend(["--date", date_text])

            subprocess.run(
                cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=sub_env, cwd=BASE_DIR,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            )
            self._json({"ok": True, "message": "Foto berhasil diganti dan di-watermark ulang."})
        except Exception as e:
            _log(f"Replace photo error: {e}")
            self._json({"ok": False, "error": str(e)}, 500)

    def _handle_timemark_koreksi_serat_optik(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            data = json.loads(body) if body else {}
            folder = data.get("folder", "")
            apply_corr = bool(data.get("apply", False))

            if not folder or not os.path.isdir(folder):
                self._json({"ok": False, "error": "Folder PDF tidak valid."}, 400)
                return

            sub_env = os.environ.copy()
            sub_env["PYTHONUNBUFFERED"] = "1"
            sub_env["PYTHONIOENCODING"] = "utf-8"

            cmd = make_script_cmd("correct_serat_optik_cores.py", [
                "--folders", folder,
                "--json"
            ])
            if apply_corr:
                cmd.append("--apply")

            res = subprocess.run(
                cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=sub_env, cwd=BASE_DIR,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            )
            items = []
            if res.stdout:
                try:
                    items = json.loads(res.stdout)
                except Exception:
                    match = re.search(r'\[\s*\{.*\}\s*\]', res.stdout, re.DOTALL)
                    if match:
                        items = json.loads(match.group(0))

            self._json({"ok": True, "items": items})
        except Exception as e:
            _log(f"Koreksi serat optik error: {e}")
            self._json({"ok": False, "error": str(e)}, 500)

    def _handle_timemark_audit_personil(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            data = json.loads(body) if body else {}
            folder = data.get("folder", "")
            action = data.get("action", "audit")
            refresh = data.get("refresh", False)

            if not folder or not os.path.isdir(folder):
                self._json({"ok": False, "error": "Folder PDF tidak valid."}, 400)
                return

            # Caching check jika action == 'audit' dan bukan refresh
            cache_file = os.path.join(APP_DATA_DIR, "audit_personnel_cache.json")
            folder_hash = str(abs(hash(os.path.normpath(folder))))[:12]

            pdf_count = 0
            newest_mtime = 0.0
            for root, dirs, fnames in os.walk(folder):
                dirs[:] = [d for d in dirs if d.lower() not in ('backups', '_temp_merged', '.git', 'node_modules')]
                for fn in fnames:
                    if fn.lower().endswith('.pdf'):
                        pdf_count += 1
                        try:
                            mt = os.path.getmtime(os.path.join(root, fn))
                            if mt > newest_mtime:
                                newest_mtime = mt
                        except Exception:
                            pass

            if action == "audit" and not refresh and os.path.isfile(cache_file):
                try:
                    with open(cache_file, "r", encoding="utf-8") as f:
                        c_dict = json.load(f)
                    c_entry = c_dict.get(folder_hash)
                    if c_entry and c_entry.get("count") == pdf_count and abs(c_entry.get("mtime", 0.0) - newest_mtime) < 0.01:
                        _log(f"Audit personil CACHE HIT for {folder} ({pdf_count} files)")
                        self._json({"ok": True, "result": c_entry.get("result"), "from_cache": True})
                        return
                except Exception as ce:
                    _log(f"Cache read error: {ce}")

            sub_env = os.environ.copy()
            sub_env["PYTHONUNBUFFERED"] = "1"
            sub_env["PYTHONIOENCODING"] = "utf-8"

            cmd = make_script_cmd("audit_and_correct_personnel.py", [
                "--folder", folder,
                "--action", action
            ])
            res = subprocess.run(
                cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=sub_env, cwd=BASE_DIR,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            )
            report = {}
            if res.stdout:
                try:
                    report = json.loads(res.stdout)
                except Exception:
                    match = re.search(r'\{.*\}', res.stdout, re.DOTALL)
                    if match:
                        report = json.loads(match.group(0))

            if not report and res.stderr:
                _log(f"Audit personil stderr: {res.stderr}")
                report = {"error": res.stderr.strip()}

            # Simpan hasil pemindaian ke cache jika berhasil
            if report and "files" in report:
                try:
                    existing_caches = {}
                    if os.path.isfile(cache_file):
                        with open(cache_file, "r", encoding="utf-8") as f:
                            existing_caches = json.load(f)
                    existing_caches[folder_hash] = {
                        "folder": folder,
                        "count": pdf_count,
                        "mtime": newest_mtime,
                        "result": report
                    }
                    _atomic_write_json(cache_file, existing_caches)
                except Exception as ce:
                    _log(f"Cache save error: {ce}")

            self._json({"ok": True, "result": report})
        except Exception as e:
            _log(f"Audit personil error: {e}")
            self._json({"ok": False, "error": str(e)}, 500)

    def _handle_timemark_export_tablo(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            data = json.loads(body) if body else {}
            folder = data.get("folder")
            export_dir = data.get("exportDir")
            year = data.get("year")
            month = data.get("month")
            preset_id = data.get("presetId") or data.get("preset_id")
            output_dir = data.get("outputDir") or data.get("outDir")

            from pathlib import Path
            out_dir = Path(output_dir) if (output_dir and os.path.isdir(output_dir)) else Path(os.path.join(BASE_DIR, "logs"))
            os.makedirs(out_dir, exist_ok=True)
            _log(f"Export Tablo request: folder={folder}, year={year}, month={month}, out_dir={out_dir}, preset={preset_id}")

            active_cfg, active_preset_name = get_active_pegawai_config(preset_id)
            active_cfg_path = os.path.join(str(out_dir), "temp_active_pegawai.json")
            try:
                with open(active_cfg_path, "w", encoding="utf-8") as f:
                    json.dump(active_cfg, f, indent=2, ensure_ascii=False)
            except Exception:
                active_cfg_path = None

            try:
                from timemark_engine.export_tablo_excel import generate_tablo_workbook
                from timemark_engine.scheduler import build_schedule, load_mapping, load_data_acuan
            except ImportError:
                sys.path.insert(0, ENGINE_DIR)
                from export_tablo_excel import generate_tablo_workbook
                from scheduler import build_schedule, load_mapping, load_data_acuan

            m_path = os.path.join(ENGINE_DIR, "asset_waktu_mapping.json")
            if not os.path.isfile(m_path) and os.path.isfile(os.path.join(BASE_DIR, "config", "asset_waktu_mapping.json")):
                m_path = os.path.join(BASE_DIR, "config", "asset_waktu_mapping.json")
            mapping = load_mapping(m_path) if os.path.isfile(m_path) else {}

            a_path = os.path.join(ENGINE_DIR, "data_acuan_tenaga_gabungan.json")
            if not os.path.isfile(a_path) and os.path.isfile(os.path.join(BASE_DIR, "config", "data_acuan_tenaga_gabungan.json")):
                a_path = os.path.join(BASE_DIR, "config", "data_acuan_tenaga_gabungan.json")
            acuan = load_data_acuan(a_path) if os.path.isfile(a_path) else {}

            sched_data = None
            if folder:
                if os.path.isfile(folder) and folder.lower().endswith(".json"):
                    with open(folder, "r", encoding="utf-8") as f:
                        sched_data = json.load(f)
                elif os.path.isdir(folder):
                    sch_cand = os.path.join(folder, "schedule.json")
                    if os.path.isfile(sch_cand):
                        with open(sch_cand, "r", encoding="utf-8") as f:
                            sched_data = json.load(f)
                        cand_p = os.path.join(BASE_DIR, "03_export_foto")
                        photos_dir = cand_p if os.path.isdir(cand_p) else os.path.join(BASE_DIR, "03_photos_export")
                        sched_data = build_schedule(
                            pdf_dir=Path(folder).resolve(),
                            photos_dir=Path(photos_dir).resolve(),
                            mapping=mapping,
                            acuan=acuan,
                            jam_mulai=7 * 60,
                            jam_selesai=18 * 60,
                            tim_max=2
                        )
                        temp_sch = os.path.join(str(out_dir), "temp_custom_schedule.json")
                        with open(temp_sch, "w", encoding="utf-8") as f:
                            json.dump(sched_data, f, indent=2, ensure_ascii=False)
            elif export_dir and os.path.isfile(os.path.join(export_dir, "schedule.json")):
                with open(os.path.join(export_dir, "schedule.json"), "r", encoding="utf-8") as f:
                    sched_data = json.load(f)

            if not sched_data or not sched_data.get("schedules"):
                err_msg = "Tidak ditemukan jadwal atau berkas PDF valid untuk diekspor ke Tablo."
                _log(f"Export Tablo failed: {err_msg}")
                self._json({"ok": False, "error": err_msg})
                return

            file_path = generate_tablo_workbook(
                sched_data,
                year=int(year) if year else None,
                month=int(month) if month else None,
                output_path=out_dir,
                config=active_cfg,
                config_path=Path(active_cfg_path) if active_cfg_path else None,
                pdf_dir=folder
            )
            _log(f"Export Tablo success: {file_path}")
            self._json({"ok": True, "filePath": str(file_path)})
        except Exception as e:
            _log(f"Export tablo error: {e}")
            import traceback
            _log(traceback.format_exc())
            self._json({"ok": False, "error": str(e)}, 500)

    def _handle_timemark_export_dinasan(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            data = json.loads(body) if body else {}
            folder = data.get("folder")
            export_dir = data.get("exportDir")
            year = data.get("year", datetime.now().year)
            month = data.get("month", datetime.now().month)
            with_personnel = data.get("withPersonnel", True)
            preset_id = data.get("presetId") or data.get("preset_id")
            output_dir = data.get("outputDir") or data.get("outDir")

            from pathlib import Path
            out_dir = Path(output_dir) if (output_dir and os.path.isdir(output_dir)) else Path(os.path.join(BASE_DIR, "logs"))
            os.makedirs(out_dir, exist_ok=True)
            _log(f"Export Dinasan request: folder={folder}, year={year}, month={month}, out_dir={out_dir}, preset={preset_id}")

            try:
                from timemark_engine.export_dinasan_excel import build_dinasan_workbook, MONTH_NAMES_ID
                from timemark_engine.scheduler import build_schedule, load_mapping, load_data_acuan
            except ImportError:
                sys.path.insert(0, ENGINE_DIR)
                from export_dinasan_excel import build_dinasan_workbook, MONTH_NAMES_ID
                from scheduler import build_schedule, load_mapping, load_data_acuan

            active_cfg, active_preset_name = get_active_pegawai_config(preset_id)
            active_cfg_path = os.path.join(str(out_dir), "temp_active_dinasan_cfg.json")
            try:
                with open(active_cfg_path, "w", encoding="utf-8") as f:
                    json.dump(active_cfg, f, indent=2, ensure_ascii=False)
            except Exception:
                active_cfg_path = os.path.join(ENGINE_DIR, "daftar_pegawai.json")

            temp_sch = os.path.join(str(out_dir), "temp_dinasan_schedule.json")
            if folder:
                if os.path.isfile(folder) and folder.lower().endswith(".json"):
                    temp_sch = folder
                elif os.path.isdir(folder):
                    sch_cand = os.path.join(folder, "schedule.json")
                    if os.path.isfile(sch_cand):
                        temp_sch = sch_cand
                    else:
                        m_path = os.path.join(ENGINE_DIR, "asset_waktu_mapping.json")
                        mapping = load_mapping(m_path) if os.path.isfile(m_path) else {}
                        a_path = os.path.join(ENGINE_DIR, "data_acuan_tenaga_gabungan.json")
                        acuan = load_data_acuan(a_path) if os.path.isfile(a_path) else {}
                        cand_d = os.path.join(BASE_DIR, "03_export_foto")
                        photos_dir_d = cand_d if os.path.isdir(cand_d) else os.path.join(BASE_DIR, "03_photos_export")
                        sched_data = build_schedule(
                            pdf_dir=Path(folder).resolve(),
                            photos_dir=Path(photos_dir_d).resolve(),
                            mapping=mapping,
                            acuan=acuan,
                            jam_mulai=7 * 60,
                            jam_selesai=18 * 60,
                            tim_max=2
                        )
                        with open(temp_sch, "w", encoding="utf-8") as f:
                            json.dump(sched_data, f, indent=2, ensure_ascii=False)
            elif export_dir and os.path.isfile(os.path.join(export_dir, "schedule.json")):
                temp_sch = os.path.join(export_dir, "schedule.json")

            m_name = MONTH_NAMES_ID.get(int(month), f"BULAN_{month}")
            out_xlsx = os.path.join(str(out_dir), f"DAFTAR_DINASAN_PEGAWAI_{m_name}_{year}.xlsx")

            build_dinasan_workbook(
                year=int(year),
                month=int(month),
                schedule_path=Path(temp_sch),
                config_path=Path(active_cfg_path),
                output_path=Path(out_xlsx),
                with_personnel=bool(with_personnel)
            )
            _log(f"Export Dinasan success: {out_xlsx}")
            self._json({"ok": True, "filePath": str(out_xlsx)})
        except Exception as e:
            _log(f"Export dinasan error: {e}")
            import traceback
            _log(traceback.format_exc())
            self._json({"ok": False, "error": str(e)}, 500)

    def _handle_timemark_open_file(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            data = json.loads(body) if body else {}
            file_path = data.get("filePath", "")
            if not file_path or not os.path.exists(file_path):
                self._json({"ok": False, "error": "Berkas tidak ditemukan."}, 404)
                return

            norm = os.path.normpath(file_path)
            os.startfile(norm)
            self._json({"ok": True})
        except Exception as e:
            _log(f"Open file error: {e}")
            self._json({"ok": False, "error": str(e)}, 500)

    def _handle_update_download(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            data = json.loads(body) if body else {}
            url = data.get("downloadUrl")
            res = updater_engine.start_download(url)
            self._json(res)
        except Exception as e:
            _log(f"Update download error: {e}")
            self._json({"error": str(e)}, 500)

    def _handle_save_dialog_file(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            data = json.loads(body)
            filename = data.get("filename", "Export.xlsx")
            b64data = data.get("data", "")
            
            save_path = _save_file_dialog_native(filename)
            if save_path:
                parent_dir = os.path.dirname(save_path)
                if parent_dir:
                    os.makedirs(parent_dir, exist_ok=True)
                raw = base64.b64decode(b64data)
                with open(save_path, "wb") as f:
                    f.write(raw)
                self._json({"ok": True, "path": save_path})
            else:
                self._json({"ok": False, "cancelled": True})
        except Exception as e:
            _log(f"Save dialog file error: {e}")
            self._json({"error": str(e)}, 500)

    def _handle_select_folder(self):
        global _selected_folder
        try:
            folder = _pick_folder_native()
            if folder:
                _selected_folder = folder
                self._json({"path": _selected_folder, "name": os.path.basename(_selected_folder)})
            else:
                self._json({"path": None, "name": None})
        except Exception as e:
            _log(f"Folder selection error: {e}")
            self._json({"error": str(e)}, 500)

    def _handle_select_file(self):
        try:
            fpath = _pick_file_native()
            if fpath:
                self._json({"path": fpath, "name": os.path.basename(fpath)})
            else:
                self._json({"path": None, "name": None})
        except Exception as e:
            _log(f"File selection error: {e}")
            self._json({"error": str(e)}, 500)

    def _handle_select_files(self):
        try:
            fpaths = _pick_files_native()
            self._json({"paths": fpaths, "items": [{"path": p, "name": os.path.basename(p)} for p in fpaths]})
        except Exception as e:
            _log(f"Multi-file selection error: {e}")
            self._json({"error": str(e)}, 500)

    def _handle_date_changer_scan(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            data = json.loads(body) if body else {}

            paths = data.get("paths", [])
            folder = data.get("folder", "")

            all_pdf_paths = []
            if folder:
                folder_str = str(folder).strip('\"\'').strip()
                if os.path.isdir(folder_str):
                    for fname in sorted(os.listdir(folder_str)):
                        if fname.lower().endswith(".pdf"):
                            all_pdf_paths.append(os.path.join(folder_str, fname))
                elif os.path.isfile(folder_str) and folder_str.lower().endswith(".pdf"):
                    all_pdf_paths.append(folder_str)
            elif paths:
                for p in paths:
                    if isinstance(p, str):
                        p_str = p.strip('\"\'').strip()
                        if os.path.isfile(p_str) and p_str.lower().endswith(".pdf"):
                            all_pdf_paths.append(p_str)
                        elif os.path.isdir(p_str):
                            for fname in sorted(os.listdir(p_str)):
                                if fname.lower().endswith(".pdf"):
                                    all_pdf_paths.append(os.path.join(p_str, fname))

            items = []
            for p in all_pdf_paths:
                info = date_changer_engine.scan_pdf_date(p)
                items.append(info)

            self._json({"ok": True, "items": items})
        except Exception as e:
            _log(f"Date changer scan error: {e}")
            self._json({"error": str(e)}, 500)

    def _handle_date_changer_apply(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            data = json.loads(body) if body else {}

            items = data.get("items", [])
            create_backup = data.get("create_backup", False)

            results = []
            success_count = 0
            error_count = 0

            for it in items:
                pdf_path = it.get("path")
                new_date = it.get("new_date")
                if not pdf_path or not new_date:
                    continue
                res = date_changer_engine.apply_date_change(pdf_path, new_date, create_backup=create_backup)
                if res.get("ok"):
                    success_count += 1
                else:
                    error_count += 1
                results.append(res)

            self._json({
                "ok": True,
                "success_count": success_count,
                "error_count": error_count,
                "results": results
            })
        except Exception as e:
            _log(f"Date changer apply error: {e}")
            self._json({"error": str(e)}, 500)

    def _handle_personnel_changer_scan(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            data = json.loads(body) if body else {}

            paths = data.get("paths", [])
            folder = data.get("folder", "")

            all_pdf_paths = []
            if folder:
                folder_str = str(folder).strip('\"\'').strip()
                if os.path.isdir(folder_str):
                    for fname in sorted(os.listdir(folder_str)):
                        if fname.lower().endswith(".pdf"):
                            all_pdf_paths.append(os.path.join(folder_str, fname))
                elif os.path.isfile(folder_str) and folder_str.lower().endswith(".pdf"):
                    all_pdf_paths.append(folder_str)
            elif paths:
                for p in paths:
                    if isinstance(p, str):
                        p_str = p.strip('\"\'').strip()
                        if os.path.isfile(p_str) and p_str.lower().endswith(".pdf"):
                            all_pdf_paths.append(p_str)
                        elif os.path.isdir(p_str):
                            for fname in sorted(os.listdir(p_str)):
                                if fname.lower().endswith(".pdf"):
                                    all_pdf_paths.append(os.path.join(p_str, fname))

            items = []
            for p in all_pdf_paths:
                info = personnel_changer_engine.scan_pdf_personnel(p)
                items.append(info)

            self._json({"ok": True, "items": items})
        except Exception as e:
            _log(f"Personnel changer scan error: {e}")
            self._json({"error": str(e)}, 500)

    def _handle_personnel_changer_apply(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            data = json.loads(body) if body else {}

            items = data.get("items", [])
            target_employees = data.get("employees", [])

            results = []
            success_count = 0
            error_count = 0

            for it in items:
                pdf_path = it.get("path")
                emp_list = it.get("employees") or target_employees
                if not pdf_path or not emp_list:
                    continue
                res = personnel_changer_engine.apply_personnel_change(pdf_path, emp_list)
                if res.get("ok"):
                    success_count += 1
                else:
                    error_count += 1
                results.append(res)

            self._json({
                "ok": True,
                "success_count": success_count,
                "error_count": error_count,
                "results": results
            })
        except Exception as e:
            _log(f"Personnel changer apply error: {e}")
            self._json({"error": str(e)}, 500)

    def _handle_timemark_schedule_list(self, parsed):
        try:
            qs = urllib.parse.parse_qs(parsed.query)
            folder = qs.get("folder", [""])[0]
            export_dir = qs.get("exportDir", [""])[0]

            # 1. Kumpulkan seluruh lokasi kandidat schedule.json
            search_candidates = []
            if folder and os.path.exists(folder):
                if os.path.isfile(folder) and folder.lower().endswith(".json"):
                    search_candidates.append(folder)
                elif os.path.isdir(folder):
                    search_candidates.extend([
                        os.path.join(folder, "schedule.json"),
                        os.path.join(os.path.dirname(folder), "schedule.json"),
                        os.path.join(os.path.dirname(os.path.dirname(folder)), "schedule.json")
                    ])
                    try:
                        exp_r, _, _ = _resolve_photo_directories(folder)
                        search_candidates.append(os.path.join(exp_r, "schedule.json"))
                    except Exception:
                        pass

            if export_dir and os.path.isdir(export_dir):
                search_candidates.extend([
                    os.path.join(export_dir, "schedule.json"),
                    os.path.join(os.path.dirname(export_dir), "schedule.json"),
                    os.path.join(os.path.dirname(os.path.dirname(export_dir)), "schedule.json")
                ])
                try:
                    exp_r2, _, _ = _resolve_photo_directories(export_dir)
                    search_candidates.append(os.path.join(exp_r2, "schedule.json"))
                except Exception:
                    pass

            default_docs = os.path.join(os.path.expanduser("~"), "Documents", "Sintelis")
            search_candidates.extend([
                os.path.join(default_docs, "schedule.json"),
                os.path.join(BASE_DIR, "schedule.json"),
                os.path.join(ENGINE_DIR, "schedule.json"),
                os.path.join(BASE_DIR, "logs", "schedule.json"),
                os.path.join(APP_DATA_DIR, "schedule.json"),
                os.path.join(os.getcwd(), "schedule.json")
            ])

            sched_path = None
            for cand in search_candidates:
                if cand and os.path.isfile(cand):
                    sched_path = cand
                    break

            if sched_path and os.path.isfile(sched_path):
                with open(sched_path, "r", encoding="utf-8") as f:
                    s_data = json.load(f)
                self._json({"ok": True, "source": sched_path, "data": s_data})
                return

            # 2. Fallback ke file_personnel_cache.json jika schedule.json belum ada
            for cand in [
                os.path.join(BASE_DIR, "logs", "file_personnel_cache.json"),
                os.path.join(APP_DATA_DIR, "file_personnel_cache.json")
            ]:
                if os.path.isfile(cand):
                    with open(cand, "r", encoding="utf-8") as f:
                        c_data = json.load(f)
                    self._json({"ok": True, "source": cand, "data": c_data})
                    return

            self._json({
                "ok": False,
                "error": "Berkas schedule.json belum ditemukan. Silakan klik tombol '⚡ Generate Jadwal Sekarang' atau jalankan Step 3 Penjadwalan pada Pipeline."
            })
        except Exception as e:
            _log(f"Schedule list error: {e}")
            self._json({"ok": False, "error": str(e)}, 500)

    def _handle_timemark_generate_schedule(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            data = json.loads(body) if body else {}

            pdf_dir = data.get("pdfDir") or data.get("folder") or ""
            export_dir = data.get("exportDir") or ""

            if not pdf_dir or not os.path.isdir(pdf_dir):
                self._json({"ok": False, "error": "Folder PDF Target belum dipilih atau tidak valid."}, 400)
                return

            export_root, photos_dir, _ = _resolve_photo_directories(export_dir or pdf_dir)
            schedule_file = os.path.join(export_root, "schedule.json")

            time_mapping = os.path.join(APP_DATA_DIR, "asset_waktu_mapping.json")
            if not os.path.isfile(time_mapping):
                time_mapping = os.path.join(ENGINE_DIR, "asset_waktu_mapping.json")
            if not os.path.isfile(time_mapping):
                time_mapping = os.path.join(ENGINE_DIR, "mapping.json")

            data_acuan = os.path.join(APP_DATA_DIR, "data_acuan_tenaga_gabungan.json")
            if not os.path.isfile(data_acuan):
                data_acuan = os.path.join(ENGINE_DIR, "data_acuan_tenaga_gabungan.json")
            if not os.path.isfile(data_acuan):
                data_acuan = os.path.join(ENGINE_DIR, "data_acuan.json")

            try:
                from timemark_engine.scheduler import build_schedule, load_mapping, load_data_acuan
            except ImportError:
                from scheduler import build_schedule, load_mapping, load_data_acuan

            mapping = load_mapping(Path(time_mapping)) if os.path.isfile(time_mapping) else {}
            acuan = load_data_acuan(Path(data_acuan)) if os.path.isfile(data_acuan) else {}

            sched = build_schedule(
                pdf_dir=Path(pdf_dir).resolve(),
                photos_dir=Path(photos_dir).resolve(),
                mapping=mapping,
                acuan=acuan,
                jam_mulai=7 * 60,
                jam_selesai=18 * 60,
                tim_max=2
            )

            os.makedirs(os.path.dirname(schedule_file), exist_ok=True)
            with open(schedule_file, "w", encoding="utf-8") as f:
                json.dump(sched, f, indent=2, ensure_ascii=False)

            # Salin juga ke folder pdf jika berbeda
            try:
                alt_file = os.path.join(pdf_dir, "schedule.json")
                if os.path.abspath(alt_file) != os.path.abspath(schedule_file):
                    with open(alt_file, "w", encoding="utf-8") as f:
                        json.dump(sched, f, indent=2, ensure_ascii=False)
            except Exception:
                pass

            total_assets = len(sched.get("schedules", []))
            self._json({
                "ok": True,
                "message": f"Berhasil membuat jadwal schedule.json ({total_assets} aset terdaftar)!",
                "source": schedule_file,
                "data": sched
            })
        except Exception as e:
            _log(f"Generate schedule error: {e}")
            self._json({"ok": False, "error": str(e)}, 500)

    def _handle_timemark_export_schedule_excel(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            data = json.loads(body) if body else {}
            folder = data.get("folder", "")

            from pathlib import Path
            sched_file = None
            if folder and os.path.isdir(folder) and os.path.isfile(os.path.join(folder, "schedule.json")):
                sched_file = Path(os.path.join(folder, "schedule.json"))
            else:
                for cand in [Path(BASE_DIR) / "schedule.json", Path(ENGINE_DIR) / "schedule.json", Path(BASE_DIR) / "logs" / "schedule.json"]:
                    if cand.is_file():
                        sched_file = cand
                        break

            if not sched_file or not sched_file.is_file():
                self._json({"ok": False, "error": "Berkas schedule.json tidak ditemukan untuk diekspor."}, 404)
                return

            default_name = f"Jadwal_Perawatan_Gabungan_{time.strftime('%Y%m%d_%H%M%S')}.xlsx"
            chosen_path = _save_file_dialog_native(default_name)
            if not chosen_path:
                self._json({"ok": False, "cancelled": True})
                return

            try:
                from timemark_engine.export_schedule_excel import generate_excel_from_schedule
            except ImportError:
                sys.path.insert(0, ENGINE_DIR)
                from export_schedule_excel import generate_excel_from_schedule

            generate_excel_from_schedule(sched_file, Path(chosen_path))

            self._json({
                "ok": True,
                "message": f"Berkas Excel jadwal berhasil disimpan ke: {os.path.basename(chosen_path)}",
                "path": chosen_path
            })
        except Exception as e:
            _log(f"Export schedule excel error: {e}")
            self._json({"ok": False, "error": str(e)}, 500)

    def _handle_save_file(self):
        global _selected_folder
        try:
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length))
            filename = str(data.get("filename", ""))
            relative = str(data.get("relativePath") or filename).replace("\\\\", "/")
            conflict = str(data.get("conflictMode") or "rename").lower()
            folder = data.get("folder") or _selected_folder
            if not folder:
                self._json({"error": "Folder tujuan penyimpanan belum ditentukan."}, 400)
                return
            if conflict not in {"rename", "skip", "overwrite"}:
                self._json({"error": "Mode konflik tidak valid."}, 400)
                return
            parts = [part for part in relative.split("/") if part]
            if not parts or any(part in {".", ".."} or ":" in part for part in parts):
                self._json({"error": "Path tujuan tidak aman."}, 400)
                return
            root = os.path.abspath(folder)
            path = os.path.abspath(os.path.join(root, *parts))
            if os.path.commonpath([root, path]) != root:
                self._json({"error": "Path tujuan berada di luar folder root."}, 400)
                return
            os.makedirs(os.path.dirname(path), exist_ok=True)
            if os.path.exists(path):
                if conflict == "skip":
                    return self._json({"ok": True, "status": "skipped", "path": path})
                if conflict == "rename":
                    stem, ext = os.path.splitext(path)
                    counter = 2
                    candidate = path
                    while os.path.exists(candidate):
                        candidate = f"{stem} ({counter}){ext}"
                        counter += 1
                    path = candidate
            raw = base64.b64decode(data.get("data", ""))
            with open(path, "wb") as f:
                f.write(raw)
            _log(f"Saved: {path}")
            self._json({"ok": True, "status": "saved", "path": path})
        except Exception as e:
            _log(f"Save file error ({filename}): {e}")
            self._json({"error": f"{filename}: {str(e)}"}, 500)

    def _handle_ocr(self):
        """Endpoint /api/ocr — OCR PDF pakai Tesseract desktop (fallback dari Tesseract.js).
        Menerima JSON: {"data": "<base64 PDF>"} → return {"text": "hasil OCR"}"""
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            data = json.loads(body)
            b64data = data.get("data", "")
            if not b64data:
                self._json({"error": "missing data field"}, 400)
                return

            # Simpan PDF sementara
            pdf_bytes = base64.b64decode(b64data)
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(pdf_bytes)
                tmp_path = tmp.name

            try:
                # Konfigurasi Tesseract & Poppler
                tess_cmd = get_tesseract_cmd()
                if os.path.exists(tess_cmd):
                    pytesseract.pytesseract.tesseract_cmd = tess_cmd
                    tessdata_dir = os.path.join(os.path.dirname(tess_cmd), "tessdata")
                    if os.path.isdir(tessdata_dir):
                        os.environ["TESSDATA_PREFIX"] = tessdata_dir

                poppler_dir = get_poppler_dir()
                # Render halaman pertama
                images = convert_from_path(
                    tmp_path, dpi=200, first_page=1, last_page=1,
                    poppler_path=poppler_dir if (poppler_dir and os.path.exists(poppler_dir)) else None
                )
                if not images:
                    self._json({"text": ""})
                    return

                img = images[0].convert("L")
                img = ImageOps.autocontrast(img)
                ww, hh = img.size
                img_crop = img.crop((0, 0, ww, int(hh * 0.40)))

                text = pytesseract.image_to_string(img_crop, lang="ind+eng").upper()
                self._json({"text": text})
            finally:
                os.unlink(tmp_path)
        except Exception as e:
            self._json({"error": str(e)}, 500)

    def _handle_p3ste_download(self):
        if _p3ste_state["running"]:
            self._json({"error": "Pengunduhan sedang berjalan"}, 400)
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            data = json.loads(body)

            nipp = str(data.get("nipp", "")).strip()
            password = str(data.get("password", "")).strip()
            curl_cmd = data.get("curl", "")
            awal = data.get("awal", "")
            akhir = data.get("akhir", "")
            type_val = data.get("type", "2")
            target_folder = data.get("folder", "")
            start_id = data.get("start_id")
            end_id = data.get("end_id")
            show_browser = data.get("show_browser", False)

            if not target_folder:
                self._json({"error": "Folder Penyimpanan wajib dipilih"}, 400)
                return

            if not nipp or not password:
                if not curl_cmd:
                    self._json({"error": "NIPP dan Kata Sandi akun login wajib diisi"}, 400)
                    return

            threading.Thread(
                target=_run_p3ste_download_task,
                args=(nipp, password, awal, akhir, type_val, target_folder, start_id, end_id, show_browser, curl_cmd),
                daemon=True
            ).start()

            self._json({"ok": True})
        except Exception as e:
            self._json({"error": str(e)}, 500)

    def _json(self, obj, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(obj).encode())
        if status >= 400:
            _log(f"API ERROR {status}: {obj.get('error', 'unknown')}")

    def log_message(self, fmt, *args):
        _log(f"HTTP: {fmt % args if args else fmt}")


def start_server():
    _log("Server thread starting (ThreadingHTTPServer)...")
    http.server.ThreadingHTTPServer.allow_reuse_address = True
    http.server.ThreadingHTTPServer.request_queue_size = 64
    try:
        with http.server.ThreadingHTTPServer(("", PORT), ApiHandler) as httpd:
            _log(f"Server listening on port {PORT}")
            httpd.serve_forever()
    except OSError as e:
        _log(f"Server notice: Port {PORT} sudah aktif atau sedang digunakan ({e}). Menggunakan server yang ada.")


_storage_lock_fd = None


def _get_safe_webview_storage():
    """Mendapatkan direktori penyimpanan WebView2 yang aman dan bebas benturan multi-instance."""
    global _storage_lock_fd
    base_storage = os.path.join(APP_DATA_DIR, "webview_storage")
    os.makedirs(base_storage, exist_ok=True)
    
    # Pembersihan direktori storage lama dari proses yang sudah mati
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        for item in os.listdir(APP_DATA_DIR):
            if item.startswith("webview_storage_") and item != "webview_storage":
                pid_str = item.replace("webview_storage_", "")
                if pid_str.isdigit():
                    handle = kernel32.OpenProcess(0x1000, False, int(pid_str))
                    if handle:
                        kernel32.CloseHandle(handle)
                    else:
                        shutil.rmtree(os.path.join(APP_DATA_DIR, item), ignore_errors=True)
    except Exception:
        pass

    # Cek apakah base_storage dapat dikunci oleh proses ini
    try:
        import msvcrt
        lock_marker = os.path.join(base_storage, ".instance_lock")
        fd = os.open(lock_marker, os.O_CREAT | os.O_RDWR)
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        _storage_lock_fd = fd
        _log(f"Using primary webview_storage: {base_storage}")
        return base_storage
    except (IOError, OSError, PermissionError) as e:
        # Jika instance lain sedang berjalan, gunakan storage terisolasi per-PID agar tidak crash 0x800700AA
        fallback_storage = os.path.join(APP_DATA_DIR, f"webview_storage_{os.getpid()}")
        os.makedirs(fallback_storage, exist_ok=True)
        _log(f"Primary webview_storage in use ({e}). Using isolated fallback: {fallback_storage}")
        return fallback_storage


def main():
    import multiprocessing
    multiprocessing.freeze_support()

    # ── CLI Script Dispatcher (Subprocess runner untuk PyInstaller frozen binary) ──
    if len(sys.argv) > 1:
        first_arg = sys.argv[1]
        target_script = None
        if first_arg.endswith(".py"):
            target_script = first_arg
            sys.argv = sys.argv[1:]
        elif first_arg in ("--run-script", "-s") and len(sys.argv) > 2:
            target_script = sys.argv[2]
            sys.argv = [sys.argv[0]] + sys.argv[3:]

        if target_script:
            if not os.path.isabs(target_script):
                candidate = os.path.join(ENGINE_DIR, target_script)
                if os.path.isfile(candidate):
                    target_script = candidate
            elif not os.path.isfile(target_script):
                candidate = os.path.join(ENGINE_DIR, os.path.basename(target_script))
                if os.path.isfile(candidate):
                    target_script = candidate

            if os.path.isfile(target_script):
                import runpy
                if ENGINE_DIR not in sys.path:
                    sys.path.insert(0, ENGINE_DIR)
                try:
                    runpy.run_path(target_script, run_name="__main__")
                except SystemExit as se:
                    sys.exit(se.code)
                except Exception as e:
                    print(f"Error running script {target_script}: {e}", file=sys.stderr)
                    sys.exit(1)
                sys.exit(0)

    _log("=== Sintelis Utility START ===")
    _log(f"Python: {sys.version}")
    _log(f"Tesseract: {TESSERACT_CMD} exists={os.path.exists(TESSERACT_CMD)}")
    _log(f"Poppler: {POPPLER_DIR} exists={os.path.exists(POPPLER_DIR)}")
    _init_persistent_storage()
    
    if not os.path.isdir(DIST_DIR):
        msg = f"Build not found at {DIST_DIR}"
        _log(f"FATAL: {msg}")
        print(f"ERROR: {msg}")
        print("Run 'npm run build' in web-app/ first.")
        sys.exit(1)

    if "--server-only" in sys.argv or os.environ.get("SERVER_ONLY") == "1":
        _log("Running in SERVER-ONLY mode (serving at http://localhost:18725)...")
        print(f"[OK] Server running in background at http://localhost:{PORT}")
        start_server()
        return

    threading.Thread(target=start_server, daemon=True).start()
    _log(f"Server started at http://localhost:{PORT}")
    print(f"[OK] Server running at http://localhost:{PORT}")
    print("[OK] Opening desktop window...")

    app_v = getattr(updater_engine, "APP_VERSION", "2.0")
    webview.create_window(
        f"Sintelis Utility 2.0 (v{app_v})",
        f"http://localhost:{PORT}",
        width=1400,
        height=900,
        resizable=True,
        min_size=(1000, 600),
    )
    _log("Window created, binding events...")
    webview.windows[0].events.minimized += on_minimized
    webview.windows[0].events.restored += on_restored
    _log("Events bound. Starting webview...")
    webview_storage = _get_safe_webview_storage()
    try:
        webview.start(private_mode=False, storage_path=webview_storage)
    except Exception as e:
        _log(f"FATAL CRASH: {e}")
        import traceback
        _log(traceback.format_exc())
        print(f"CRASH: {e}")
    finally:
        global _storage_lock_fd
        if _storage_lock_fd is not None:
            try:
                import msvcrt
                msvcrt.locking(_storage_lock_fd, msvcrt.LK_UNLCK, 1)
                os.close(_storage_lock_fd)
            except Exception:
                pass
            _storage_lock_fd = None
    _log("=== Sintelis Utility END ===")
    print("[OK] Window closed.")


if __name__ == "__main__":
    main()
