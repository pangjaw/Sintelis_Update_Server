import os
import sys
import time
import json
import shutil
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WEBAPP_DIR = os.path.join(SCRIPT_DIR, "web-app")
SERVER_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "02_server_update"))

print("==================================================")
print("  BUILD & DEPLOY SINTELIS UTILITY DESKTOP APP     ")
print("  Target: C:\\Users\\SINTEL 1.21 BOO\\Documents\\Server\\Sintelis_Update_Server\\02_server_update")
print("==================================================")

# 1. Clean old exe in dist
dist_exe = os.path.join(WEBAPP_DIR, "dist", "SintelisUtility.exe")
if os.path.exists(dist_exe):
    try:
        os.remove(dist_exe)
        print("[1/4] Berkas exe lama di dist/ berhasil dibersihkan.")
    except Exception as e:
        print("[WARN] Gagal menghapus exe lama:", e)

# 2. PyInstaller build
print("[2/4] Menjalankan PyInstaller compile (mohon tunggu ~60-90s)...")
cmd = [sys.executable, "-m", "PyInstaller", "--clean", "build_exe.spec"]
res = subprocess.run(cmd, cwd=WEBAPP_DIR)
if res.returncode != 0:
    print("[ERROR] PyInstaller gagal mengompilasi!")
    sys.exit(1)

if not os.path.exists(dist_exe):
    print("[ERROR] SintelisUtility.exe tidak ditemukan di dist/!")
    sys.exit(1)

# 3. Validasi ukuran biner
size_bytes = os.path.getsize(dist_exe)
size_mb = size_bytes / (1024 * 1024)
print(f"[3/4] Validasi ukuran: {size_bytes} bytes ({size_mb:.2f} MB)")
if size_mb < 170 or size_mb > 250:
    print(f"[WARN] Ukuran biner di luar rentang normal 170-250 MB: {size_mb:.2f} MB")

# 4. Copy ke 02_server_update
print("[4/4] Menyalin biner ke 02_server_update...")
target_exe = os.path.join(SERVER_DIR, "SintelisUtility.exe")
copied = False
for attempt in range(1, 20):
    try:
        shutil.copyfile(dist_exe, target_exe)
        copied = True
        break
    except PermissionError:
        print(f"  [WAIT] File target sedang terkunci, mencoba kembali ({attempt}/20)...")
        time.sleep(1.5)

if not copied:
    print("[ERROR] Gagal menyalin ke target_exe karena file terkunci.")
    sys.exit(1)

print(f"  -> Biner aktif disalin ke: {target_exe}")

# Sinkronisasi version.json
v_src = os.path.join(SERVER_DIR, "version.json")
if os.path.exists(v_src):
    # Dapatkan versi terkini dari updater_engine
    app_version = "1.7.2"
    try:
        sys.path.insert(0, WEBAPP_DIR)
        import updater_engine
        app_version = getattr(updater_engine, "APP_VERSION", "1.7.2")
    except Exception:
        pass

    with open(v_src, "r", encoding="utf-8") as f:
        v_data = json.load(f)
    v_data["version"] = app_version
    v_data["fileSize"] = size_bytes
    v_data["releaseDate"] = time.strftime("%Y-%m-%d")
    v_data["downloadUrl"] = f"https://update.sintelboo.my.id/SintelisUtility.exe?v={app_version}"
    v_data["changelog"] = [
        f"v{app_version}: Audit & Koreksi Personil Berdasarkan Tim - Pencocokan jadwal Tim 1, Tim 2, Tim 3 dari schedule.json & rotasi profil pegawai",
        f"v{app_version}: Koreksi Sesuai Tim - Otomatis sinkronkan personil Tim 2 dan Tim 3 tanpa bentrok dengan Tim 1",
        f"v{app_version}: UI Koreksi Dokumen - Tombol 'Scan Ulang & Audit Tim', filter visual, kolom Tim, dan personil seharusnya",
        f"v{app_version}: Audit Personil - OCR Fallback otomatis untuk membaca berkas PDF hasil scan / bitmap"
    ]
    with open(v_src, "w", encoding="utf-8") as f:
        json.dump(v_data, f, indent=2, ensure_ascii=False)
    print(f"  -> version.json diperbarui ke v{app_version} di: {v_src}")

print("[SUKSES] Build dan rilis berhasil disiapkan secara eksklusif di Drive C!")
