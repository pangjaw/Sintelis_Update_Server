# 🏛️ ARSITEKTUR SISTEM SINTELIS UTILITY

## 1. Komponen Utama
Sistem Sintelis Utility terdiri dari tiga pilar utama:
1. **Desktop App Client (`SintelisUtility.exe`)**:
   - Frontend: React 18, Vite, Lucide Icons, NeuroNest CSS.
   - Backend Runtime: Python 3.14 embedded dengan `pywebview` / MS Edge WebView2.
   - Modul Utama:
     - Menu 1: Ganti Nama PDF Ceklis
     - Menu 2: Download P3-STE & Audit Berkas
     - Menu 3: Pipeline Foto Timemark & Galeri Interaktif
     - Menu 4: Ubah Tanggal Dokumen (Date Changer 3 Titik)
2. **Update Server (`server_update.py`)**:
   - HTTP Server Python pada Port 8085 dengan dukungan CORS lengkap.
   - Melayani endpoint `https://update.sintelboo.my.id/version.json` dan file binary rilis.
3. **Pipeline Jaringan (Cloudflare Zero Trust Tunnel)**:
   - Menghubungkan hostname publik `update.sintelboo.my.id` ke localhost port 8085 di PC Server tanpa perlu port-forwarding router publik.

## 2. Diagram Alur Pembaruan Otomatis (In-Place Auto-Update)
```mermaid
sequenceDiagram
    participant Klien as SintelisUtility.exe (Klien)
    participant CF as Cloudflare Tunnel
    participant Server as Update Server (Port 8085)

    Klien->>CF: GET /version.json
    CF->>Server: Forward ke 127.0.0.1:8085
    Server-->>Klien: Return version & fileSize
    Note over Klien: Perbandingan SemVer (Server > Klien)
    opt Jika Ada Pembaruan
        Klien->>CF: Download SintelisUtility.exe?v=X.Y.Z
        CF->>Server: Streaming Binary (189 MB)
        Server-->>Klien: Binary Downloaded ke AppData Temp
        Klien->>Klien: Spawn PowerShell in-place updater script
        Klien->>Klien: Terminate process & Overwrite active EXE
        Klien->>Klien: Relaunch new SintelisUtility.exe
    end
```
