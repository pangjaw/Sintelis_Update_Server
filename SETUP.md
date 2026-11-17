# 🖥️ Hardware_Setup.md — Panduan Pemindaian Hardware & Akselerasi LaMa AI

> **Referensi Konfigurasi Perangkat Baru (`Sintelis_Update_Server`)**  
> Berkas ini memuat prosedur pemindaian perangkat keras, pemilihan *execution provider* ONNX Runtime, serta arsitektur cache model LaMa AI.

---

## 1. Aturan Pemindaian Hardware & Setup Multi-Device

Setiap kali AI Agent diminta melakukan konfigurasi, instalasi dependensi, atau optimasi di PC baru, **AI AGENT WAJIB**:
1. Memindai hardware PC target terlebih dahulu (GPU, VRAM, CPU, dan RAM).
2. Menyajikan ringkasan spesifikasi hardware kepada User.
3. Memberikan 3 opsi setup yang dapat dipilih User sesuai kebutuhan perangkat.

### Skrip Pemindaian Otomatis
Jalankan skrip pembantu:
```powershell
python 01_scripts_pendukung/setup_ai_hardware.py