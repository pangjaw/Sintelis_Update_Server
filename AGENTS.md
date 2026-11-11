# 📋 AGENTS.md — PANDUAN KERJA & INDEKS PENGETAHUAN PROYEK

> **Instruksi Wajib untuk Seluruh AI Agent (Antigravity / Gemini / Claude)**  
> Berkas ini adalah pintu gerbang (*entry point*) utama. Setiap agen yang bekerja pada repositori `Sintelis_Update_Server` **wajib membaca dan memahami berkas ini terlebih dahulu**.

---

## 🗺️ 1. PETA DOKUMEN PROYEK (DOCUMENTATION INDEX)

Proyek ini mendokumentasikan seluruh logika bisnis, arsitektur, dan alur fiturnya ke dalam berkas-berkas Markdown di folder `03_vault_docs/`.  
Setiap kali AI Agent menerima tugas, **baca berkas-berkas berikut sesuai ruang lingkup tugas yang diberikan**:

| Berkas Dokumentasi | Peran & Ruang Lingkup | Kapan Agen Wajib Membaca? |
| :--- | :--- | :--- |
| 🏛️ **[03_vault_docs/Architecture.md](file:///D:/02.%20Sintelis/UPT%20Resor%20Sintelis%201.21%20Bogor/Server/Sintelis_Update_Server/03_vault_docs/Architecture.md)** | **Arsitektur Sistem & Komponen Teknis**<br>• 3 Pilar: Desktop Client (WebView2), Resident Daemon (`58253`), Update Server (`8085`).<br>• Alur Cloudflare Zero Trust Tunnel.<br>• Mekanisme inpaint LaMa AI & Sibling Consensus.<br>• Optimasi garbage collection & kompresi PDF. | Wajib dibaca saat: memodifikasi server update, daemon background, alur inferensi AI, atau struktur internal PDF. |
| 📜 **[03_vault_docs/Feature_Specs_and_Rules.md](file:///D:/02.%20Sintelis/UPT%20Resor%20Sintelis%201.21%20Bogor/Server/Sintelis_Update_Server/03_vault_docs/Feature_Specs_and_Rules.md)** | **Spesifikasi Fitur & Aturan Logika Bisnis**<br>• Durasi dinas per kategori aset (OTB, PDSE, Catu Daya, dll.).<br>• Aturan alokasi jam kerja Multi-Tim (Tim 1 & Tim 2).<br>• Format penamaan file, stempel tanggal watermark, dan pemisahan folder foto (*Photo Splitting*).<br>• Aturan funcloc SAP & pemetaan lokasi. | Wajib dibaca saat: menangani ekspor Excel dinasan, tablo, parsing nama file, stempel tanggal foto, atau penggabungan PDF. |
| 📦 **[03_vault_docs/Update_SOP.md](file:///D:/02.%20Sintelis/UPT%20Resor%20Sintelis%201.21%20Bogor/Server/Sintelis_Update_Server/03_vault_docs/Update_SOP.md)** | **Prosedur Operasional Pembaruan (SOP Release)**<br>• Langkah pembuatan biner `SintelisUtility.exe`.<br>• Prosedur pengujian rilis dan deploy ke server pembaruan.<br>• Skema *in-place auto-updater* klien. | Wajib dibaca saat: mempersiapkan instruksi rilis untuk User atau mengaudit mekanisme pembaruan aplikasi. |
| 📊 **[03_vault_docs/Dashboard.md](file:///D:/02.%20Sintelis/UPT%20Resor%20Sintelis%201.21%20Bogor/Server/Sintelis_Update_Server/03_vault_docs/Dashboard.md)** | **Status Modul & Pelacak Proyek**<br>• Daftar status modul aktif (Menu 1 s.d Menu 4).<br>• Catatan perbaikan terkini dan rencana fitur selanjutnya. | Wajib dibaca saat: mengecek status menyeluruh aplikasi dan riwayat perubahan besar. |
| 🤖 **[GEMINI.md](file:///D:/02.%20Sintelis/UPT%20Resor%20Sintelis%201.21%20Bogor/Server/Sintelis_Update_Server/GEMINI.md)** | **Panduan Operasional & Etika Coding Universal**<br>• Prinsip Zero Assumptions, Zero Regression, KISS/YAGNI.<br>• Protokol keamanan dan gaya komunikasi AI. | Wajib dibaca sebagai: panduan etika coding dan metodologi kerja AI Agent. |

---

## 🚫 2. ATURAN BAKU BUILD & RELEASE (DILARANG AUTO-BUILD)

### 2.1 Dilarang Menjalankan Build Biner Desktop Otomatis
Setelah AI menyelesaikan pembaruan fitur (*feature update*), refactoring, atau perbaikan bug (*bugfix*):
* **AI DILARANG KERAS** mengeksekusi skrip build rilis:
  * ❌ `build_and_deploy.bat`
  * ❌ `python build_release.py`
  * ❌ `pyinstaller build_exe.spec`
* **BIARKAN USER SAJA YANG MELAKUKAN BUILD SECARA MANUAL** setelah memeriksa hasil pekerjaan AI.

### 2.2 Batas Toleransi Pekerjaan AI
* AI **hanya diizinkan** melakukan kompilasi aset frontend Vite (`cmd /c "npm --prefix 01_scripts_pendukung\web-app run build"`) untuk memastikan tidak ada galat sintaks/JSX sebelum giliran selesai.
* Setelah itu, AI wajib menginstruksikan kepada User bahwa kode telah siap dan User dapat menjalankan `build_and_deploy.bat` sendiri secara manual jika diinginkan.

### 2.3 Mengapa Aturan Ini Ditetapkan?
1. **Mencegah Tabrakan Antar Sesi (*Race Condition / File Locking*):**
   * Terdapat kemungkinan lebih dari satu sesi chat aktif secara bersamaan pada repositori yang sama.
   * Proses PyInstaller membutuhkan waktu 60–90 detik dan mengunci (*lock*) berkas `dist/SintelisUtility.exe` serta `02_server_update/SintelisUtility.exe`. Jika dijalankan paralel, proses akan crash dengan galat `PermissionError: [WinError 32]` atau menghasilkan biner korup.
2. **Kontrol Kualitas Rilis:**
   * User memegang kendali penuh atas kapan biner siap dirilis ke server pembaruan (port 8085).

---

## 🖥️ 3. ATURAN PEMINDAIAN HARDWARE & SETUP MULTI-DEVICE

Setiap kali AI Agent diminta melakukan konfigurasi, instalasi dependensi, atau optimasi di PC baru, **AI AGENT WAJIB**:
1. Memindai hardware PC target terlebih dahulu (GPU, VRAM, CPU, dan RAM).
2. Menyajikan ringkasan spesifikasi hardware kepada User.
3. Memberikan 3 opsi setup yang dapat dipilih User sesuai kebutuhan perangkat.

### 🔍 Skrip Pemindaian Otomatis
Jalankan skrip pembantu:
```powershell
python 01_scripts_pendukung/setup_ai_hardware.py
```
Skrip ini akan otomatis mendeteksi apakah PC menggunakan GPU NVIDIA, GPU Non-NVIDIA (AMD/Intel), atau murni CPU/RAM.

---

## 🚀 4. PILIHAN SETUP AKSELERASI LAMA AI

### Opsi 1: NVIDIA GPU (CUDA 11.8 + cuDNN 8.9) — Rekomendasi Tercepat (~0.7s - 1.2s per foto)
Khusus PC / Laptop dengan kartu grafis NVIDIA (GTX 1050/1060/1070/1080/1650, RTX 20xx/30xx/40xx/50xx, Quadro).
* **Rekomendasi Python**: Python 3.11 (64-bit).
* **Perintah Instalasi**:
```powershell
python -m pip install onnxruntime-gpu==1.18.0 nvidia-cuda-runtime-cu11 nvidia-cublas-cu11 nvidia-cudnn-cu11==8.9.5.29 nvidia-cufft-cu11
```
* **Kelebihan**: Beban komputasi AI dialihkan 100% ke GPU VRAM, tidak membebani CPU, inferensi sangat kilat.

### Opsi 2: CPU & RAM Saja (Standard PC / GPU Non-NVIDIA AMD & Intel) (~3.5s - 7.0s per foto)
Untuk PC kantor standar, PC server tanpa kartu grafis, laptop dengan GPU bawaan Intel HD/UHD, serta laptop/PC dengan kartu grafis AMD Radeon.
* **Rekomendasi Python**: Python 3.10 – 3.12 (atau Python 3.11/3.14).
* **Perintah Instalasi**:
```powershell
python -m pip uninstall -y onnxruntime-gpu onnxruntime-directml
python -m pip install onnxruntime==1.18.0
```
* **Catatan Khusus DirectML**: Arsitektur *Fast Fourier Convolution* (FFC) pada model LaMa Inpainting memiliki operator tensor kompleks yang **belum didukung oleh HLSL shader DirectX 12 DirectML** (akan memicu galat `DmlExecutionProvider 80070057 The parameter is incorrect`). Oleh karena itu, PC non-NVIDIA (AMD/Intel) wajib diarahkan ke **CPU Execution Provider** yang terbukti 100% stabil.

---

### ⚙️ Konfigurasi Provider Execution Universal
Di dalam kode Python (`edit_timemark_ide1.py` & `timemark_resident_service.py`), urutan provider diset:
```python
providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
session = ort.InferenceSession(model_path, sess_options=opts, providers=providers)
```
Sistem akan otomatis memilih akselerasi tertinggi yang terpasang pada PC:
1. Jika ada paket CUDA dan kartu NVIDIA -> Jalan di CUDA (VRAM).
2. Jika tidak ada CUDA / kartu non-NVIDIA -> Otomatis fallback ke CPU tanpa menimbulkan crash/galat.

### ⚡ Arsitektur Resident Worker & SSD Model Cache
* Model LaMa AI otomatis di-cache ke Drive C: (SSD) di `%LOCALAPPDATA%\Sintelis\models\lama_fp32.onnx`.
* Service resident `timemark_resident_service.py` otomatis dijalankan di latar belakang oleh `run_desktop_webview.py` pada port `127.0.0.1:58253`.
* Model tetap berada di RAM/VRAM sehingga proses *Hapus Teks* berjalan instan tanpa jeda cold-start.
