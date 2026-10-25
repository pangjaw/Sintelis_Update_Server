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
print(f"  Target: {SERVER_DIR}")
print("==================================================")

# 0. Build Frontend Vite (npm install & npm run build)
npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
node_modules_dir = os.path.join(WEBAPP_DIR, "node_modules")
if not os.path.isdir(node_modules_dir):
    print("[0/4] Menginstal dependensi frontend (npm install)...")
    res_npm_i = subprocess.run([npm_cmd, "install"], cwd=WEBAPP_DIR)
    if res_npm_i.returncode != 0:
        print("[ERROR] npm install gagal!")
        sys.exit(1)

print("[0.5/4] Mengompilasi frontend React/Vite (npm run build)...")
res_npm_b = subprocess.run([npm_cmd, "run", "build"], cwd=WEBAPP_DIR)
if res_npm_b.returncode != 0:
    print("[ERROR] npm run build gagal!")
    sys.exit(1)

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
if size_mb < 170 or size_mb > 270:
    print(f"[WARN] Ukuran biner di luar rentang normal 170-270 MB: {size_mb:.2f} MB")

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
        # Fallback rename swap jika file sedang dibuka oleh aplikasi aktif
        try:
            old_cand = target_exe + ".old"
            if os.path.exists(old_cand):
                try: os.remove(old_cand)
                except Exception: pass
            os.rename(target_exe, old_cand)
            shutil.copyfile(dist_exe, target_exe)
            try: os.remove(old_cand)
            except Exception: pass
            copied = True
            break
        except Exception:
            pass
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
    app_version = "1.9.0"
    try:
        sys.path.insert(0, WEBAPP_DIR)
        import updater_engine
        app_version = getattr(updater_engine, "APP_VERSION", "1.9.0")
    except Exception:
        pass

    with open(v_src, "r", encoding="utf-8") as f:
        v_data = json.load(f)
    v_data["version"] = app_version
    v_data["fileSize"] = size_bytes
    v_data["releaseDate"] = time.strftime("%Y-%m-%d")
    v_data["downloadUrl"] = f"https://update.sintelboo.my.id/SintelisUtility.exe?v={app_version}"
    v_data["changelog"] = [
        f"v{app_version}: Fix Ubah Personil & No. SC - Perbaikan presisi layout sel tabel (deteksi garis drawings dinamis, eliminasi overlap shape putih pada garis tabel), pemulihan font DejaVuSans-Bold, dan standardisasi ukuran teks (Nama 7.8, No. SC 7.0)",
        f"v{app_version}: Fix Ubah Personil & No. SC - Perbaikan error perhitungan panjang teks font kustom (Font 'dejavusans-bold' is unsupported) saat penimpaan personil PDF",
        f"v{app_version}: Perbaikan Menyeluruh Auto-Crop Kolase 2x2 & 3-in-1 - Ambang batas seam adaptif, smart auto-quadrant detection ke kuadran Bottom-Left (BL), fallback instan single crop ✂️, dan sinkronisasi preview mentah/editan terpotong",
        f"v{app_version}: Fitur Salin Log (Copy to Clipboard) - Tombol 1-klik salin log pada Console Pipeline dan seluruh window log terminal",
        f"v{app_version}: Window Log Real-Time Koreksi Dokumen & Core Serat Optik - Output step-by-step proses audit personil dan koreksi core",
        f"v{app_version}: Early Binding Multi-Tanggal Menyeluruh - Deteksi frekuensi inspeksi terpadu pada WESEL, PDSE, PTDS, PTLS, SINYAL, AXC",
        f"v{app_version}: Isolasi File Ganda Hari Sama (_part{{n}}) - Berkas bertanda (2).pdf otomatis mendapat suffix _part2 mencegah saling timpa"
    ]

    with open(v_src, "w", encoding="utf-8") as f:
        json.dump(v_data, f, indent=2, ensure_ascii=False)
    print(f"  -> version.json diperbarui ke v{app_version} di: {v_src}")

print(f"[SUKSES] Build dan rilis berhasil disiapkan di {SERVER_DIR}!")
