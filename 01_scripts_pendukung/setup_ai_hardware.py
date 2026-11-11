# -*- coding: utf-8 -*-
"""
Setup & Diagnostik Akselerasi Hardware LaMa AI (Sintelis Utility)
Mendeteksi spesifikasi hardware PC (NVIDIA, AMD, Intel, atau CPU/RAM)
dan memberikan rekomendasi atau instalasi otomatis paket akselerasi yang tepat.
"""

import sys
import os
import subprocess
import platform

def detect_hardware():
    gpus = []
    total_ram_gb = 0
    cpu_name = platform.processor()

    # Query WMI via PowerShell (Windows)
    try:
        cmd_gpu = ["powershell", "-NoProfile", "-Command", 
                   "Get-CimInstance Win32_VideoController | Select-Object -Property Name, AdapterRAM"]
        res_gpu = subprocess.run(cmd_gpu, capture_output=True, text=True, errors="replace")
        for line in res_gpu.stdout.splitlines():
            line = line.strip()
            if line and not line.startswith("Name") and not line.startswith("----"):
                parts = line.rsplit(None, 1)
                name = parts[0].strip()
                vram_bytes = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
                vram_gb = round(vram_bytes / (1024**3), 2)
                gpus.append({"name": name, "vram_gb": vram_gb})
    except Exception as e:
        print(f"[Warning] Gagal query GPU via PowerShell: {e}")

    try:
        cmd_ram = ["powershell", "-NoProfile", "-Command", 
                   "[math]::Round((Get-CimInstance Win32_OperatingSystem).TotalVisibleMemorySize / 1024 / 1024, 2)"]
        res_ram = subprocess.run(cmd_ram, capture_output=True, text=True, errors="replace")
        total_ram_gb = float(res_ram.stdout.strip())
    except Exception:
        total_ram_gb = 8.0

    try:
        cmd_cpu = ["powershell", "-NoProfile", "-Command", 
                   "(Get-CimInstance Win32_Processor).Name"]
        res_cpu = subprocess.run(cmd_cpu, capture_output=True, text=True, errors="replace")
        cpu_name = res_cpu.stdout.strip()
    except Exception:
        pass

    return {
        "gpus": gpus,
        "ram_gb": total_ram_gb,
        "cpu": cpu_name,
        "python_version": platform.python_version()
    }

def print_hardware_summary(hw):
    print("=" * 65)
    print(" 🖥️  HASIL PEMINDAIAN HARDWARE PC (SINTELIS AI ACCELERATION)")
    print("=" * 65)
    print(f" • Versi Python : {hw['python_version']} ({platform.architecture()[0]})")
    print(f" • Processor    : {hw['cpu']}")
    print(f" • Kapasitas RAM: {hw['ram_gb']} GB")
    print(" • Kartu Grafis (GPU):")
    if not hw['gpus']:
        print("   - Tidak terdeteksi kartu grafis dedicated.")
    else:
        for idx, g in enumerate(hw['gpus'], 1):
            vram_str = f"({g['vram_gb']} GB VRAM)" if g['vram_gb'] > 0 else ""
            print(f"   [{idx}] {g['name']} {vram_str}")
    print("-" * 65)

def get_recommendation(hw):
    has_nvidia = any("nvidia" in g["name"].lower() or "geforce" in g["name"].lower() or "quadro" in g["name"].lower() for g in hw["gpus"])

    if has_nvidia:
        return "cuda", "NVIDIA GPU Terdeteksi (Akselerasi CUDA 11.8)", [
            "python -m pip install onnxruntime-gpu==1.18.0 nvidia-cuda-runtime-cu11 nvidia-cublas-cu11 nvidia-cudnn-cu11==8.9.5.29 nvidia-cufft-cu11"
        ]
    else:
        return "cpu", "CPU / RAM Mode (Stabil untuk semua CPU & GPU Non-NVIDIA)", [
            "python -m pip uninstall -y onnxruntime-gpu onnxruntime-directml",
            "python -m pip install onnxruntime==1.18.0"
        ]

def run_commands(cmds):
    for cmd in cmds:
        print(f"\n[Menjalankan]: {cmd}")
        res = subprocess.run(cmd, shell=True)
        if res.returncode != 0:
            print(f"[Error] Perintah gagal dengan kode keluar: {res.returncode}")
            return False
    return True

def main():
    hw = detect_hardware()
    print_hardware_summary(hw)

    rec_mode, rec_reason, rec_cmds = get_recommendation(hw)

    print(" 🎯 REKOMENDASI MODE AKSELERASI LAMA AI:")
    print(f" Status: {rec_reason}")
    print()
    print(" Pilihan Setup Tersedia:")
    print("   1. [Opsi 1] NVIDIA CUDA (Khusus GPU NVIDIA GeForce / RTX / GTX / Quadro)")
    print("      Performa: KILAT (~0.7s - 1.2s per foto) | Menggunakan GPU VRAM.")
    print("      Syarat   : Python 3.11 (64-bit) + CUDA 11.8 + cuDNN 8.9.")
    print()
    print("   2. [Opsi 2] CPU & RAM Optimized (Universal untuk AMD, Intel, atau PC Kantor)")
    print("      Performa: STABIL (~3.5s - 7.0s per foto) | Kompatibel 100% tanpa error.")
    print("      Catatan  : Arsitektur Fast Fourier Convolution (FFC) pada LaMa AI belum didukung")
    print("                 oleh DirectML (menimbulkan error MatMul 80070057), sehingga untuk GPU")
    print("                 Non-NVIDIA (AMD/Intel) wajib diarahkan ke CPU Execution Provider.")
    print("=" * 65)

    if len(sys.argv) > 1 and sys.argv[1].lower() in ("--auto", "-y", "--cuda", "--cpu"):
        arg = sys.argv[1].lower()
        if arg in ("--auto", "-y"):
            choice = rec_mode
        elif arg == "--cuda":
            choice = "cuda"
        else:
            choice = "cpu"
    else:
        rec_num = "1" if rec_mode == "cuda" else "2"
        choice_input = input(f"\nPilih mode setup [1 / 2] (Default Rekomendasi: {rec_num}): ").strip()
        if not choice_input:
            choice_input = rec_num

        if choice_input == "1":
            choice = "cuda"
        else:
            choice = "cpu"

    if choice == "cuda":
        print("\n>>> Mengonfigurasi untuk: NVIDIA GPU (CUDA 11.8 + cuDNN 8.9)...")
        cmds = [
            "python -m pip install onnxruntime-gpu==1.18.0 nvidia-cuda-runtime-cu11 nvidia-cublas-cu11 nvidia-cudnn-cu11==8.9.5.29 nvidia-cufft-cu11"
        ]
    else:
        print("\n>>> Mengonfigurasi untuk: CPU / RAM Saja...")
        cmds = [
            "python -m pip uninstall -y onnxruntime-gpu onnxruntime-directml",
            "python -m pip install onnxruntime==1.18.0"
        ]

    success = run_commands(cmds)
    if success:
        print("\n✅ Setup hardware selesai! LaMa AI siap digunakan secara optimal pada PC ini.")
    else:
        print("\n❌ Terjadi kendala saat instalasi. Pastikan koneksi internet aktif dan pip terbarukan.")

if __name__ == "__main__":
    main()
