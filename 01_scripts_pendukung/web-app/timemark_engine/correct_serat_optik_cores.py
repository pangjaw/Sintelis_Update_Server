"""correct_serat_optik_cores.py — Koreksi Nilai Jumlah Core Dokumen Serat Optik.

Aturan Koreksi:
1. Khusus Serat Optik JPL: Core = 12 (kunci tetap 12 core).
2. Serat Optik OTB (Stasiun/Petak): Core = Total Aset OTB * 24 Core.

Fitur:
- Pemindaian kilat khusus file dengan nama 'SERAT OPTIK' atau 'OTB'.
- True PDF Redaction presisi (menjaga garis outline tabel kiri dan kanan 100% utuh).
- Penulisan teks menggunakan font DejaVuSans (7.202 pt, regular) rata tengah.
- Pencadangan otomatis ke backups/ sebelum file diubah.
- Mendukung CLI dan mode JSON untuk Web Dashboard.
"""
import os
import sys
import re
import json
import shutil
import argparse
from pathlib import Path
from datetime import datetime

# Pastikan UTF-8 encoding pada Windows Console
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import fitz

APP_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = APP_DIR / "config"
FONT_PATH = CONFIG_DIR / "DejaVuSans.ttf"
BACKUP_DIR = APP_DIR / "backups"

# Koordinat batas sel HASIL standar pada checklist Serat Optik
# Garis batas vertikal kiri: ~535.6, kanan: ~565.6
CELL_LEFT_BORDER = 535.64
CELL_RIGHT_BORDER = 565.65
CELL_CENTER_X = (CELL_LEFT_BORDER + CELL_RIGHT_BORDER) / 2.0  # ~550.645
REDACT_X0 = 537.0  # Berjarak aman 1.4 pt dari garis kiri
REDACT_X1 = 564.0  # Berjarak aman 1.6 pt dari garis kanan
FONT_SIZE = 7.202


def ensure_font():
    """Pastikan font DejaVuSans.ttf tersedia di folder config/."""
    global FONT_PATH
    if FONT_PATH.exists():
        return
    candidates = [
        Path(__file__).resolve().parent / "DejaVuSans.ttf",
        Path(__file__).resolve().parent / "DejaVuSans-Bold.ttf",
    ]
    for c in candidates:
        if c.exists():
            FONT_PATH = c
            return
    try:
        import matplotlib
        mpl_font = Path(matplotlib.__file__).parent / "mpl-data" / "fonts" / "ttf" / "DejaVuSans.ttf"
        if mpl_font.exists():
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(str(mpl_font), str(FONT_PATH))
    except Exception:
        pass


def is_serat_optik_file(path: Path) -> bool:
    """Filter cepat berbasis nama file."""
    name_upper = path.name.upper()
    return ("SERAT OPTIK" in name_upper or "SERAT_OPTIK" in name_upper or "OTB" in name_upper) and path.suffix.lower() == ".pdf"


def extract_assets_from_page1(page) -> list[str]:
    """Ekstrak daftar funcloc aset di header Halaman 1."""
    text = page.get_text() or ""
    header_part = text.split("Lokasi")[0] if "Lokasi" in text else text[:500]
    lines = [l.strip() for l in header_part.split("\n") if l.strip()]
    
    asset_lines = []
    seen = set()
    for l in lines:
        if any(k in l for k in [":", "OTB", "TRA", "JPL", "TLK"]) and not any(k in l for k in ["STE", "PERAWATAN", "BULANAN", "Tanggal", "Periode"]):
            if l not in seen:
                seen.add(l)
                asset_lines.append(l)
    return asset_lines


def get_core_info(pdf_path: Path) -> dict | None:
    """Membaca informasi aset, nilai core saat ini, dan nilai target core."""
    if not pdf_path.exists():
        return None

    try:
        doc = fitz.open(str(pdf_path))
        if len(doc) == 0:
            return None
        page = doc[0]
        
        assets = extract_assets_from_page1(page)
        
        # Deteksi apakah JPL
        name_upper = pdf_path.name.upper()
        is_jpl = "JPL" in name_upper or any("JPL" in a.upper() for a in assets)
        
        if is_jpl:
            target_core = 12
            tipe = "JPL"
        else:
            asset_count = max(1, len(assets))
            target_core = asset_count * 24
            tipe = "OTB"
        
        # Cari nilai core saat ini pada tabel
        blocks = page.get_text("dict")["blocks"]
        target_y0 = None
        target_y1 = None
        
        for b in blocks:
            if "lines" not in b: continue
            for l in b["lines"]:
                for s in l["spans"]:
                    if s["text"].strip() == "Jumlah Core":
                        target_y0, target_y1 = s["bbox"][1], s["bbox"][3]
                        break
                if target_y0 is not None: break
            if target_y0 is not None: break
        
        current_core = None
        has_field = target_y0 is not None
        
        if has_field:
            for b in blocks:
                if "lines" not in b: continue
                for l in b["lines"]:
                    for s in l["spans"]:
                        if abs(s["bbox"][1] - target_y0) < 6 and s["bbox"][0] > 530:
                            txt = s["text"].strip()
                            if txt.isdigit():
                                current_core = int(txt)
                            else:
                                current_core = txt
                            break
                    if current_core is not None: break
                if current_core is not None: break
        
        doc.close()
        
        needs_correction = (current_core != target_core)
        
        return {
            "file": str(pdf_path),
            "filename": pdf_path.name,
            "tipe": tipe,
            "assets": assets,
            "asset_count": len(assets),
            "current_core": current_core,
            "target_core": target_core,
            "needs_correction": needs_correction,
            "has_field": has_field
        }
    except Exception as e:
        return {
            "file": str(pdf_path),
            "filename": pdf_path.name,
            "error": str(e),
            "needs_correction": False
        }


def scan_folder(folder_path: Path) -> list[dict]:
    """Pindai seluruh berkas Serat Optik di folder secara kilat."""
    if not folder_path.exists():
        return []
    
    results = []
    # Rekursif rglob hanya untuk pdf
    for p in sorted(folder_path.rglob("*.pdf")):
        if is_serat_optik_file(p):
            info = get_core_info(p)
            if info:
                # Tambahkan relatif folder untuk tampilan
                try:
                    rel_dir = str(p.parent.relative_to(APP_DIR))
                except Exception:
                    rel_dir = str(p.parent)
                info["folder"] = rel_dir
                results.append(info)
    return results


def apply_core_correction(pdf_path: Path, target_core: int, make_backup: bool = True) -> tuple[bool, str]:
    """Terapkan perbaikan nilai Jumlah Core pada berkas PDF."""
    ensure_font()
    if not pdf_path.exists():
        return False, "File tidak ditemukan"

    try:
        # 1. Backup jika diminta
        if make_backup:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            b_dir = BACKUP_DIR / f"serat_optik_cores_{ts}"
            b_dir.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(str(pdf_path), str(b_dir / pdf_path.name))
        
        doc = fitz.open(str(pdf_path))
        page = doc[0]
        
        # Cari baris 'Jumlah Core'
        blocks = page.get_text("dict")["blocks"]
        target_s = None
        for b in blocks:
            if "lines" not in b: continue
            for l in b["lines"]:
                for s in l["spans"]:
                    if s["text"].strip() == "Jumlah Core":
                        target_s = s
                        break
                if target_s: break
            if target_s: break
        
        if not target_s:
            doc.close()
            return False, "Baris 'Jumlah Core' tidak ditemukan di Halaman 1"
        
        row_y0 = target_s["bbox"][1]
        row_y1 = target_s["bbox"][3]
        row_origin_y = target_s["origin"][1]
        
        # Redaksi aman di dalam sel HASIL (tidak menyentuh garis batas kiri 535.6 atau kanan 565.6)
        safe_redact_rect = fitz.Rect(REDACT_X0, row_y0 - 2.5, REDACT_X1, row_y1 + 2.5)
        page.add_redact_annot(safe_redact_rect, fill=(1, 1, 1))
        page.apply_redactions()
        
        # Masukkan teks nilai baru rata tengah
        text_to_insert = str(target_core)
        
        if FONT_PATH.exists():
            custom_font = fitz.Font(fontfile=str(FONT_PATH))
            page.insert_font(fontname="dejavu_core", fontfile=str(FONT_PATH))
            text_w = custom_font.text_length(text_to_insert, fontsize=FONT_SIZE)
            font_name_use = "dejavu_core"
        else:
            text_w = fitz.get_text_length(text_to_insert, fontname="helv", fontsize=FONT_SIZE)
            font_name_use = "helv"
        
        x_origin = CELL_CENTER_X - (text_w / 2.0)
        
        page.insert_text((x_origin, row_origin_y), text_to_insert, fontname=font_name_use, fontsize=FONT_SIZE, color=(0, 0, 0))
        
        # Simpan dokumen ke file sementara lalu timpa file asli
        temp_path = pdf_path.with_name(f"{pdf_path.stem}_tmp_{os.getpid()}.pdf")
        doc.save(str(temp_path), garbage=3, deflate=True)
        doc.close()
        shutil.move(str(temp_path), str(pdf_path))
        return True, "Berhasil dikoreksi"
    except Exception as e:
        return False, f"Error: {str(e)}"


def main():
    parser = argparse.ArgumentParser(description="Koreksi Jumlah Core Serat Optik")
    parser.add_argument("--folders", nargs="+", help="Folder-folder yang ingin dipindai/dikoreksi")
    parser.add_argument("--file", type=str, help="Satu file PDF spesifik")
    parser.add_argument("--scan", action="store_true", help="Hanya pindai dan tampilkan hasil tanpa mengubah file")
    parser.add_argument("--apply", action="store_true", help="Terapkan perbaikan nilai core")
    parser.add_argument("--no-backup", action="store_true", help="Jangan buat backup sebelum apply")
    parser.add_argument("--json", action="store_true", help="Keluarkan output dalam format JSON")
    args = parser.parse_args()

    ensure_font()

    # Kumpulkan daftar file
    target_files = []
    if args.file:
        p = Path(args.file)
        if p.exists() and p.is_file():
            target_files.append(p)
    elif args.folders:
        for fld in args.folders:
            f_path = Path(fld)
            if not f_path.is_absolute():
                f_path = APP_DIR / f_path
            if f_path.exists():
                for p in sorted(f_path.rglob("*.pdf")):
                    if is_serat_optik_file(p):
                        target_files.append(p)
    else:
        # Default scan 05_pdf_merged, 01_pdf_source, 02_pdf_target jika ada
        for def_fld in ["05_pdf_merged", "01_pdf_source", "02_pdf_target"]:
            p = APP_DIR / def_fld
            if p.exists():
                for pf in sorted(p.rglob("*.pdf")):
                    if is_serat_optik_file(pf):
                        target_files.append(pf)

    # Hilangkan duplikat path
    target_files = sorted(list(set(target_files)))

    # Jalankan scan
    items = []
    for tf in target_files:
        info = get_core_info(tf)
        if info:
            try:
                rel = str(tf.parent.relative_to(APP_DIR))
            except Exception:
                rel = str(tf.parent)
            info["folder"] = rel
            items.append(info)

    if args.apply:
        applied_count = 0
        failed_count = 0
        for item in items:
            if item.get("needs_correction"):
                pdf_p = Path(item["file"])
                ok, msg = apply_core_correction(pdf_p, item["target_core"], make_backup=not args.no_backup)
                item["applied"] = ok
                item["message"] = msg
                if ok:
                    applied_count += 1
                    item["current_core"] = item["target_core"]
                    item["needs_correction"] = False
                else:
                    failed_count += 1
            else:
                item["applied"] = False
                item["message"] = "Sudah sesuai, dilewati"

    if args.json:
        print(json.dumps(items, indent=2, ensure_ascii=False))
    else:
        print(f"=== LAPORAN KOREKSI CORE SERAT OPTIK ({len(items)} berkas) ===")
        for idx, it in enumerate(items, 1):
            status_str = "⚠️ PERLU KOREKSI" if it.get("needs_correction") else "✅ SUDAH SESUAI"
            if args.apply and it.get("applied"):
                status_str = "⚡ BERHASIL DIKOREKSI"
            print(f"[{idx}/{len(items)}] {it['filename']}")
            print(f"  ├── Folder : {it.get('folder', '-')}")
            print(f"  ├── Tipe   : {it.get('tipe', '-')} ({it.get('asset_count', 0)} aset)")
            print(f"  ├── Core   : Saat ini={it.get('current_core')} -> Target={it.get('target_core')}")
            print(f"  └── Status : {status_str}")


if __name__ == "__main__":
    main()
