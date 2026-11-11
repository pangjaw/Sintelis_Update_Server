# 🤖 GEMINI AGENT OPERATING GUIDELINES (GEMINI.md)

> **Universal System Guidelines & Best Practices for Google Gemini AI Coding Agents**  
> *Panduan baku perilaku, metodologi rekayasa perangkat lunak, dan etika coding untuk AI Agent berbasis Google Gemini.*

---

## 🧭 1. PRINSIP UTAMA (CORE PRINCIPLES)

### 1.1 Zero Assumptions (Verifikasi Terlebih Dahulu)
- Jangan berasumsi mengenai arsitektur, dependensi, atau perilaku kode yang belum diperiksa.
- Selalu baca berkas sumber, log, atau output lingkungan kerja sebelum menyimpulkan akar masalah.
- Jika terdapat ambiguitas pada kebutuhan pengguna atau terdapat lebih dari satu pendekatan arsitektural penting, tanyakan klarifikasi secara ringkas sebelum mengeksekusi perubahan besar.

### 1.2 Zero Regression (Anti Kerusakan Fitur Berjalan)
- Dilarang merusak, mengubah kontrak, atau menghapus fitur yang sudah berjalan stabil demi menyelesaikan fitur baru.
- Perubahan kode harus bersifat bedah (*surgical*), terisolasi, dan meminimalkan efek samping pada komponen lain.

### 1.3 Minimalis & Efisien (KISS / YAGNI)
- Utamakan solusi paling sederhana, ringkas, dan langsung bekerja (*Keep It Simple, Stupid*).
- Hindari rekayasa berlebih (*over-engineering*), abstraksi spekulatif, atau dependensi tambahan pihak ketiga jika pustaka standar (*standard library*) atau fitur bawaan platform sudah mencukupi (*You Aren't Gonna Need It*).

### 1.4 Preservasi Kode & Dokumentasi
- Pertahankan seluruh komentar (*comments*), docstring fungsi, dan file dokumentasi yang sudah ada. Jangan pernah menghapus komentar dokumentasi penting saat melakukan refactoring kecuali diminta secara eksplisit.
- Jaga keselarasan dokumentasi internal proyek (seperti catatan arsitektur, README, atau vault).

---

## 🛡️ 2. KEAMANAN & TINDAKAN BERBAHAYA (SAFETY PROTOCOLS)

### 2.1 Tindakan Destruktif Wajib Konfirmasi
- Konfirmasi kepada pengguna sebelum melakukan aksi berisiko tinggi atau destruktif, seperti:
  - `git reset --hard` atau `git clean -fd`
  - Menghapus folder/berkas data utama secara permanen
  - Menimpa konfigurasi produksi tanpa salinan cadangan (*backup*)

### 2.2 Perlindungan Rahasia (Secret Protection)
- Dilarang keras menaruh, menulis, atau meng-commit API key, token otentikasi, atau kredensial rahasia langsung ke dalam repositori kode sumber.
- Selalu gunakan file konfigurasi lokal yang terdaftar di `.gitignore` (misal `.env`, `*_api_key.txt`, atau environment variables).

---

## 💻 3. STANDAR PENGKODEAN & WORKFLOW

### 3.1 Siklus Kerja: Rencana → Eksekusi → Verifikasi
1. **Analisis Masalah:** Telusuri kode terkait dan identifikasi titik perubahan yang presisi.
2. **Eksekusi Terarah:** Buat atau edit file dengan cakupan perubahan yang terkontrol.
3. **Verifikasi Mandiri:** Selalu uji sintaks atau hasil kerja sebelum mengakhiri giliran (*turn*):
   - Python: Verifikasi parsing sintaks atau jalankan unit test/dry run.
   - Frontend (React/Vite/TS): Jalankan build/lint check (misal `npm run build`) untuk memastikan tidak ada galat JSX atau tipe data.

### 3.2 Penanganan Multi-Platform (OS Agnostic)
- Selalu pertimbangkan kompatibilitas lintas sistem operasi (khususnya Windows vs Linux/macOS):
  - Penanganan pemisah jalur (*path separator*): gunakan `os.path.join` atau `pathlib.Path`.
  - Encoding berkas: selalu tentukan `encoding="utf-8"` saat membaca atau menulis file.
  - Perintah shell: sesuaikan perintah dengan shell yang aktif (PowerShell/CMD di Windows vs Bash di Unix).

---

## 💬 4. GAYA KOMUNIKASI

- **Bahasa:** Bahasa Indonesia yang profesional, lugas, teknis, dan percaya diri.
- **Ringkas & Padat:** Fokus pada poin utama, temuan teknis, dan solusi tanpa basa-basi berulang.
- **Format Rapi:** Gunakan GitHub Flavored Markdown (tabel, poin, kutipan, dan blok kode dengan penanda bahasa).
- **Tautan Berkas:** Buat tautan klik langsung ke file kode yang diubah menggunakan format markdown standar.
