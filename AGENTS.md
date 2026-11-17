# 📋 AGENTS.md — PANDUAN KERJA OTOMATIS & INDEKS PROYEK

> **Instruksi Wajib untuk Seluruh AI Agent (Hermes / Gemini / Claude / Antigravity)**  
> Berkas ini adalah SOP utama repositori `Sintelis_Update_Server`. Setiap kali User melaporkan bug, meminta fitur baru, atau memulai sesi baru, **wajib jalankan alur kerja di bawah ini secara otomatis**.

---

## 🔄 1. ALUR KERJA OTOMATIS (BUG / UPDATE / FITUR BARU)

Setiap kali User menyampaikan laporan bug atau permintaan pembaruan aplikasi, jalankan 3 tahap ini secara berurutan:

### Tahap A: Analisa & Pembuatan Rencana (Jangan Langsung Ubah Kode)
1. **Investigasi Hemat Context:** Gunakan maksimal 2–3 sub-agent (jika perlu) untuk melacak akar masalah. Baca file target hanya pada rentang baris yang relevan (`grep` / `read_file` ±30 baris). Dilarang membuat skrip eksperimen berulang (`probe_v*.py`).
2. **Tulis `PLAN.md` (Maks. ~150–200 baris):**
   - Jika `PLAN.md` lama sudah selesai, pindahkan isinya ke `PLAN_ARSIP.md` terlebih dahulu.
   - Tulis `PLAN.md` baru berisi: **Goal**, **Akar Masalah & Bukti**, **Daftar Task Berurutan** (nama file + rentang baris target + cara verifikasi), dan **Mitigasi Risiko**.
   - Jika ada pilihan parameter/desain yang ambigus, **pilih langsung default paling aman** sesuai pola kode eksisting (jangan berhenti menunggu blocker pertanyaan).
3. **Reset `PROGRESS.md`:** Tulis ulang `PROGRESS.md` berisi daftar checkbox `[ ] Task 1`, `[ ] Task 2`, dst., lengkap dengan path file target dan perintah verifikasinya.
4. **Catat Hasil Analisa ke Obsidian Vault (`03_vault_docs/Changelog_dan_Bugfix.md`):**
   - Tambahkan entri baru di bagian paling atas berisi tanggal, gejala bug/permintaan update, dan ringkasan akar masalah yang ditemukan.
5. **BERHENTI & LAPOR:** Setelah `PLAN.md`, `PROGRESS.md`, dan catatan analisa di vault selesai ditulis, **berhenti sebelum mengedit kode produksi** dan minta konfirmasi User untuk mulai eksekusi.

### Tahap B: Eksekusi Bertahap (Saat User Menyuruh Lanjut / Eksekusi)
1. Baca `PROGRESS.md` dan **HANYA** bagian Task aktif di `PLAN.md` (dilarang memuat seluruh `PLAN.md` atau file besar seperti `run_desktop_webview.py` secara utuh).
2. Kerjakan maksimal **2–3 Task per giliran** secara berurutan:
   - Wajib baca teks aktual file target sebelum melakukan `patch` agar tidak terjadi `old_string` mismatch.
   - Verifikasi setiap perubahan (`python -m py_compile` untuk Python / `cmd /c "npm --prefix 01_scripts_pendukung\web-app run build"` untuk frontend).
   - Ubah status `[ ]` menjadi `[x]` di `PROGRESS.md` setiap kali 1 Task lulus.
3. **BERHENTI setelah maksimal 3 Task** dan laporkan:
   - Ringkasan perubahan & `git diff --stat`.
   - Sisa Task pending di `PROGRESS.md`.
   - Indikator beban context sesi ini (beri peringatan eksplisit jika disarankan menjalankan `/new` di Discord sebelum batch berikutnya).

### Tahap C: Penutupan & Dokumentasi Obsidian Vault (Setelah Semua Task Selesai)
1. Pastikan seluruh Task di `PROGRESS.md` berstatus `[x]`.
2. **Update Obsidian Vault (`03_vault_docs/`):**
   - Lengkapi entri di `03_vault_docs/Changelog_dan_Bugfix.md` dengan detail solusi yang diterapkan, daftar file yang diubah, dan status verifikasi.
   - Perbarui `03_vault_docs/Dashboard.md` (dan `Feature_Specs_and_Rules.md` / `Architecture.md` jika ada perubahan alur fitur/arsitektur).
3. Tampilkan `git status --short` dan `git diff --stat` sebagai laporan akhir kepada User.

---

## 🗺️ 2. PETA DOKUMEN OBSIDIAN VAULT (`03_vault_docs/`)

Baca dokumen di `03_vault_docs/` **hanya pada bagian yang relevan** dengan tugas aktif:

| Berkas Dokumentasi | Peran & Ruang Lingkup | Referensi Saat Menangani |
| :--- | :--- | :--- |
| 📝 **`03_vault_docs/Changelog_dan_Bugfix.md`** | **Log Otomatis AI Agent:** Riwayat analisa akar masalah, perbaikan bug, dan update fitur per tanggal. | Wajib diperbarui di Tahap A (analisa) dan Tahap C (selesai eksekusi). |
| 📊 **`03_vault_docs/Dashboard.md`** | Daftar status modul aktif (Menu 1–4) dan ringkasan perbaikan besar. | Cek status menyeluruh aplikasi & update saat fitur selesai. |
| 🏛️ **`03_vault_docs/Architecture.md`** | 3 Pilar (WebView2, Resident Daemon `58253`, Update Server `8085`), Cloudflare Tunnel, LaMa AI & Sibling Consensus, kompresi PDF. | Server update, daemon background, inferensi AI, atau struktur internal PDF. |
| 📜 **`03_vault_docs/Feature_Specs_and_Rules.md`** | Durasi dinas aset, alokasi Multi-Tim, penamaan file, stempel tanggal watermark, *Photo Splitting*, funcloc SAP. | Ekspor Excel dinasan, tablo, parsing nama file, stempel tanggal, atau merge PDF. |
| 📦 **`03_vault_docs/Update_SOP.md`** | Pembuatan biner `SintelisUtility.exe`, pengujian rilis, dan skema *auto-updater* klien. | Audit mekanisme rilis/update aplikasi. |
| 🖥️ **`03_vault_docs/Hardware_Setup.md`** | Pemindaian GPU/CPU (`setup_ai_hardware.py`), instalasi CUDA 11.8 vs CPU ONNX (larangan DirectML), dan cache SSD LaMa AI. | Instalasi dependensi atau konfigurasi di PC baru. |
| 🤖 **`GEMINI.md`** | Prinsip Zero Assumptions, Zero Regression, KISS/YAGNI, dan etika coding. | Panduan metodologi kerja agen. |

---

## 🚫 3. ATURAN BAKU BUILD & RELEASE (DILARANG AUTO-BUILD)

* **AI DILARANG KERAS** menjalankan `build_and_deploy.bat`, `python build_release.py`, atau `pyinstaller build_exe.spec` (mencegah *file locking* `WinError 32` pada `SintelisUtility.exe` dan menjaga kendali rilis di tangan User).
* **Batas Toleransi AI:** Hanya boleh menjalankan build frontend Vite (`cmd /c "npm --prefix 01_scripts_pendukung\web-app run build"`) untuk cek galat sintaks/JSX, lalu instruksikan User melakukan build biner secara manual.