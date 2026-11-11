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

---

## 🚀 PANDUAN SETUP GPU ACCELERATION (NVIDIA CUDA)

Jika proyek ini akan dipasang atau dideploy ke PC/laptop lain yang memiliki kartu grafis NVIDIA (seperti GTX 1050 atau lebih tinggi):

### 1. Rekomendasi Lingkungan Python
* **Gunakan Python 3.11 (64-bit)** (atau rentang Python 3.10 – 3.12).
* ⚠️ **Hindari Python 3.14+** untuk inferensi GPU saat ini, karena pustaka biner resmi (`onnxruntime-gpu`, `paddlepaddle-gpu`) belum menyediakan wheel Windows untuk versi tersebut.

### 2. Perintah Instalasi Pustaka GPU (CUDA 11.8 + cuDNN 8.9 Universal)
Jalankan perintah berikut di lingkungan Python 3.11:
```powershell
python -m pip install onnxruntime-gpu==1.18.0 nvidia-cuda-runtime-cu11 nvidia-cublas-cu11 nvidia-cudnn-cu11==8.9.5.29 nvidia-cufft-cu11
```
> [!NOTE]
> **Mengapa Menggunakan Kombinasi Ini?**
> * Kartu grafis seperti NVIDIA GTX 1050 (arsitektur Pascal, Compute Capability 6.1) tidak mendukung *cuDNN v9 Frontend Graph API* (akan crash dengan galat `CUDNN_FE failure 11: CUDNN_BACKEND_API_FAILED`).
> * Kombinasi `onnxruntime-gpu==1.18.0` + CUDA 11.8 + cuDNN 8.9.5 adalah standar paling stabil di industri: bekerja 100% mulus baik di GPU generasi Pascal (GTX 1050/1060/1070/1080) maupun GPU modern (RTX 20xx, 30xx, 40xx, 50xx).
> * Jika PC target tidak memiliki kartu NVIDIA, ONNXRuntime otomatis beralih (*fallback*) ke `CPUExecutionProvider`.

### 3. Registrasi DLL CUDA di Python
Agar Windows dapat menemukan pustaka biner `cublasLt64_12.dll` dan `cudart64_12.dll` dari paket pip, muat direktori DLL sebelum mengimpor `onnxruntime`:
```python
import os
import site

# Tambahkan direktori bin paket NVIDIA ke DLL search path
for sp in site.getsitepackages():
    for sub in ["nvidia/cuda_runtime/bin", "nvidia/cublas/bin", "nvidia/cudnn/bin"]:
        p = os.path.join(sp, sub.replace("/", os.sep))
        if os.path.isdir(p) and hasattr(os, "add_dll_directory"):
            try:
                os.add_dll_directory(p)
            except Exception:
                pass
```

### 4. Konfigurasi Provider Execution
Prioritaskan provider GPU dengan fallback otomatis ke CPU:
```python
providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
session = ort.InferenceSession(model_path, providers=providers)
```
Jika GPU/CUDA tidak tersedia pada PC target, ONNXRuntime akan otomatis beralih ke `CPUExecutionProvider` tanpa menimbulkan galat.

### 5. Arsitektur Resident Worker & SSD Model Cache
Untuk performa inferensi kilat (~0.7s – 1.5s per foto vs ~50s mode cold subprocess):
* Model LaMa AI otomatis di-cache ke Drive C: (SSD) di `%LOCALAPPDATA%\Sintelis\models\lama_fp32.onnx`.
* Service resident `timemark_resident_service.py` otomatis dijalankan di latar belakang oleh `run_desktop_webview.py` pada port `127.0.0.1:58253`.
* Model PaddleOCR tetap berada di RAM dan sesi ONNX CUDA tetap berada di GPU VRAM, siap memproses foto secara instan tanpa cold-restart.

