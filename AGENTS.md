# 📋 WORKSPACE RULES — SINTELIS UPDATE SERVER

> **Aturan Wajib untuk Semua Sesi Chat & AI Agent (Antigravity)**  
> Berlaku untuk seluruh direktori kerja proyek `Sintelis_Update_Server`.

---

## 🚫 ATURAN BAKU BUILD & RELEASE (DILARANG AUTO-BUILD)

### 1. Dilarang Menjalankan Build Biner Desktop Otomatis
Setelah AI menyelesaikan pembaruan fitur (*feature update*), refactoring, atau perbaikan bug (*bugfix*):
* **AI DILARANG KERAS** mengeksekusi skrip build rilis:
  * ❌ `build_and_deploy.bat`
  * ❌ `python build_release.py`
  * ❌ `pyinstaller build_exe.spec`
* **BIARKAN USER SAJA YANG MELAKUKAN BUILD SECARA MANUAL** setelah memeriksa hasil pekerjaan AI.

### 2. Batas Toleransi Pekerjaan AI
* AI **hanya diizinkan** melakukan kompilasi aset frontend Vite (`npm run build`) untuk memastikan tidak ada galat sintaks/JSX sebelum turn selesai.
* Setelah itu, AI wajib menginstruksikan kepada User bahwa kode telah siap dan User dapat menjalankan `build_and_deploy.bat` sendiri secara manual jika diinginkan.

### 3. Mengapa Aturan Ini Ditetapkan?
1. **Mencegah Tabrakan Antar Chat (*Race Condition / File Locking*):**
   * Terdapat kemungkinan lebih dari satu sesi chat aktif secara bersamaan pada repositori yang sama.
   * Proses PyInstaller membutuhkan waktu 60–90 detik dan mengunci (*lock*) berkas `dist/SintelisUtility.exe` serta `02_server_update/SintelisUtility.exe`. Jika dijalankan paralel, proses akan crash dengan galat `PermissionError: [WinError 32]` atau menghasilkan biner korup.
2. **Kontrol Kualitas Rilis:**
   * User memegang kendali penuh atas kapan biner siap dirilis ke server pembaruan (port 8085).

---

## 🛡️ ATURAN TEKNIS LAINNYA
* **Zero Regression**: Dilarang menghapus atau mengubah kontrak alur fitur yang telah tertera di `03_vault_docs/Feature_Specs_and_Rules.md`.
* **Preservasi Dokumentasi**: Pertahankan seluruh komentar kode, docstring, dan dokumentasi vault yang sudah ada.
