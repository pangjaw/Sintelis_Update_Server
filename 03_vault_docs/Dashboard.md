# 🧭 SINTELIS UTILITY & UPDATE SERVER DASHBOARD
> **Pusat Kendali Aplikasi Desktop & Peladen Pembaruan Otomatis (Cloudflare Auto-Updater)**
> Terakhir Diperbarui: 2026-10-16 14:09:00 | Versi Aktif: **v1.7.0**

---

## ⚡ Status Sistem Terintegrasi
- **Lokasi Utama Proyek & Server:** `C:\Users\SINTEL 1.21 BOO\Documents\Server\Sintelis_Update_Server`
- **Direktori Output Rilis & HTTP Server:** `C:\Users\SINTEL 1.21 BOO\Documents\Server\Sintelis_Update_Server\02_server_update` (Port 8085)
- **Status Cloudflare Zero Trust Tunnel:** Forwarding `https://update.sintelboo.my.id` -> `127.0.0.1:8085`
- **Target Rilis Biner:** `SintelisUtility.exe` (~181.61 MB)
- **Catatan Migrasi:** Jalur lama `D:\Sintelis_Update_Server` telah dinonaktifkan/dipindahkan sepenuhnya ke direktori ini.

---

## 📂 Struktur Direktori Proyek

```text
Sintelis_Update_Server/
│
├── 📁 01_scripts_pendukung/        <-- Source Code & Utilitas Desktop App
│   ├── web-app/                    <-- Frontend Vite/React & Backend run_desktop_webview.py
│   ├── Aplikasi/                   <-- Pustaka Eksternal Poppler DLL
│   ├── data-aset/                  <-- Acuan Master Aset Resor 1.21 BOO
│   ├── build_release.py            <-- Skrip Otomasi Kompilasi PyInstaller (Target: 02_server_update)
│   └── requirements.txt            <-- Ketergantungan Modul Python
│
├── 📁 02_server_update/            <-- SATU-SATUNYA TARGET OUTPUT RILIS & SERVER UPDATE
│   ├── SintelisUtility.exe         <-- Biner Rilis Aktif v1.7.0 (181.61 MB)
│   ├── version.json                <-- Manifest Versi & Changelog Klien
│   ├── server_update.py            <-- Script HTTP Server Port 8085 (CORS Enabled)
│   ├── start_update_server.bat     <-- Skrip Start Server Manual
│   └── run_update_server.vbs       <-- Silent Background Launcher
│
├── 📁 03_vault_docs/               <-- Dokumentasi Obsidian & SOP
│   ├── Dashboard.md                <-- File Ini (Beranda Utama Vault)
│   ├── Architecture.md             <-- Spesifikasi Arsitektur Sistem
│   ├── Update_SOP.md               <-- SOP 6 Aturan Emas Rilis Biner
│   └── Notes/                      <-- Catatan Harian & Log Perubahan
│
├── 📁 .obsidian/                   <-- Konfigurasi Obsidian Vault
├── 📄 build_and_deploy.bat         <-- Skrip Eksekusi 1-Klik Build & Deploy
└── 📄 README.md                    <-- Panduan Cepat Proyek
```

---

## 🚀 Panduan Operasional Cepat

### Cara Build dan Rilis Versi Baru (1-Klik)
Cukup jalankan file batch di root folder:
```cmd
build_and_deploy.bat
```
Skrip akan secara otomatis:
1. Mengompilasi frontend React & membungkus Python backend via PyInstaller di `01_scripts_pendukung`.
2. Memvalidasi ukuran file biner (180–195 MB).
3. Menyalin biner langsung ke `02_server_update\SintelisUtility.exe`.
4. Memperbarui timestamp dan ukuran di `02_server_update\version.json`.
5. Me-restart proses peladen pembaruan port 8085.

---

## 🔗 Tautan Navigasi Vault
- [[Architecture|Arsitektur Sistem]]
- [[Update_SOP|SOP 6 Aturan Emas Pembaruan]]
- [[Notes/Daily/2026-10-16|Log Pemindahan & Penataan Direktori]]
