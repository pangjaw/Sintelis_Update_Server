"""correct_serat_optik_cores.py — Koreksi Nilai Jumlah Core Dokumen Serat Optik (Multi-Kolom & Single-Kolom).

Aturan Koreksi Berdasarkan Master Database:
1. Sesuai Database OTB Core (Cilebut, Bogor, Telkom Bogor, JPL).
2. Format penulisan: HANYA ANGKA (misal: "48", "24", "12"), tanpa kata "Core".
3. Aset di luar database (seperti OTB BOP, BTT, COS, MSG, CGB, dll.): Default = 24.
4. Seluruh berkas JPL (yang tidak tercantum di database): Default = 12.
5. Mendukung format Single-Kolom (1 aset) maupun Multi-Kolom (2, 3, 5 aset) dengan grid dinamis.
6. True PDF Redaction presisi (menjaga garis outline tabel kiri dan kanan 100% utuh).
7. Penulisan teks menggunakan font DejaVuSans (7.202 pt, regular) rata tengah.
8. Pencadangan otomatis ke backups/ sebelum file diubah.
9. Mendukung CLI dan mode JSON untuk Web Dashboard.
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

import warnings
warnings.filterwarnings("ignore", category=FutureWarning)
try:
    import pymupdf as fitz
except ImportError:
    import fitz

APP_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = APP_DIR / "config"
FONT_PATH = CONFIG_DIR / "DejaVuSans.ttf"
BACKUP_DIR = APP_DIR / "backups"
DB_JSON_PATH = Path(__file__).resolve().parent / "otb_core_database.json"

# Master Database Fallback
MASTER_BY_FUNLOC = {
    # CILEBUT
    "TRA11799": 48, "TRA11833": 48, "TRA11852": 48, "TRA11866": 48,
    "TRA11875": 12, "TRA11884": 12, "TRA11891": 24, "TRA11897": 12,
    "TRA11902": 12, "TRA11814": 24, "TRA11819": 24, "TRA11824": 24, "TRA11827": 24,
    # BOGOR
    "TRA11796": 48, "TRA11830": 24, "TRA11849": 48, "TRA11863": 24,
    "TRA11872": 24, "TRA11881": 12, "TRA11889": 24, "TRA11895": 12,
    "TRA11900": 24, "TRA11812": 24, "TRA11817": 24, "TRA11822": 24,
    # TELKOM BOGOR
    "TRA11803": 12, "TRA11838": 24, "TRA11856": 12
}

MASTER_BY_NAME = {
    # CILEBUT
    "OTB 1 ER CILEBUT": 48, "OTB 2 ER CILEBUT": 48, "OTB 3 ER CILEBUT": 48, "OTB 4 ER CILEBUT": 48,
    "OTB 5 ER CILEBUT": 12, "OTB 6 ER CILEBUT": 12, "OTB 7 ER CILEBUT": 24, "OTB 8 ER CILEBUT": 12,
    "OTB 9 ER CILEBUT": 12, "OTB 10 ER CILEBUT": 24, "OTB 11 ER CILEBUT": 24, "OTB 12 ER CILEBUT": 24, "OTB 13 ER CILEBUT": 24,
    # BOGOR
    "OTB 1 ER BOGOR": 48, "OTB 2 ER BOGOR": 24, "OTB 3 ER BOGOR": 48, "OTB 4 ER BOGOR": 24,
    "OTB 5 ER BOGOR": 24, "OTB 6 ER BOGOR": 12, "OTB 7 ER BOGOR": 24, "OTB 8 ER BOGOR": 12,
    "OTB 9 ER BOGOR": 24, "OTB 10 ER BOGOR": 24, "OTB 11 ER BOGOR": 24, "OTB 12 ER BOGOR": 24,
    # TELKOM BOGOR
    "OTB 1 ER TELKOM BOGOR": 12, "OTB 2 ER TELKOM BOGOR": 24, "OTB 3 ER TELKOM BOGOR": 12,
    # JPL
    "JPL 01": 12, "JPL 28": 12, "JPL 27": 12, "JPL 26N": 12
}

DEFAULT_JPL_CORE = 12
DEFAULT_STATION_CORE = 24

# Parameter Grid Tabel Checklist Standar
# Batas vertikal paling kanan tabel selalu 565.65 pt
GRID_RIGHT_BORDER = 565.65
GRID_COL_WIDTH = 48.61
FONT_SIZE = 7.202


def load_database():
    """Memuat database dari JSON jika ada, atau fallback ke konstanta python."""
    global MASTER_BY_FUNLOC, MASTER_BY_NAME, DEFAULT_JPL_CORE, DEFAULT_STATION_CORE
    if DB_JSON_PATH.exists():
        try:
            with open(DB_JSON_PATH, encoding="utf-8") as f:
                data = json.load(f)
                if "by_funloc" in data:
                    MASTER_BY_FUNLOC.update(data["by_funloc"])
                if "by_name" in data:
                    MASTER_BY_NAME.update(data["by_name"])
                if "defaults" in data:
                    DEFAULT_JPL_CORE = data["defaults"].get("jpl", 12)
                    DEFAULT_STATION_CORE = data["defaults"].get("station", 24)
        except Exception:
            pass


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


def get_target_core_for_asset(funloc: str, name: str, is_jpl: bool = False) -> int:
    """Mencari target nilai core dari database dengan fallback stasiun=24 / jpl=12."""
    funloc_clean = (funloc or "").strip().upper()
    if funloc_clean in MASTER_BY_FUNLOC:
        return MASTER_BY_FUNLOC[funloc_clean]

    name_clean = (name or "").strip().upper()
    for k, v in MASTER_BY_NAME.items():
        if k in name_clean or name_clean in k:
            return v

    if is_jpl or "JPL" in name_clean or "JPL" in funloc_clean:
        return DEFAULT_JPL_CORE

    return DEFAULT_STATION_CORE


def extract_header_assets(page) -> list[str]:
    """Ekstrak daftar funcloc aset di header Halaman 1."""
    text = page.get_text() or ""
    header_part = text.split("Lokasi")[0] if "Lokasi" in text else text[:600]
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
    """Membaca informasi tabel, kolom aset, nilai core saat ini, dan target core per kolom."""
    if not pdf_path.exists():
        return None

    try:
        load_database()
        doc = fitz.open(str(pdf_path))
        if len(doc) == 0:
            return None
        page = doc[0]

        assets = extract_header_assets(page)
        name_upper = pdf_path.name.upper()
        is_jpl = "JPL" in name_upper or any("JPL" in a.upper() for a in assets)

        blocks = page.get_text("dict")["blocks"]

        # 1. Cari baris Nomor Aset, Nama ODF/OTB (1.1), dan Jumlah Core (1.2)
        y_nomor_aset = None
        y_nama = None
        y_core = None
        target_s = None

        for b in blocks:
            if "lines" not in b: continue
            for l in b["lines"]:
                for s in l["spans"]:
                    txt = s["text"].strip()
                    if "Nomor Aset" in txt and y_nomor_aset is None:
                        y_nomor_aset = s["bbox"][1]
                    elif txt == "Jumlah Core" and y_core is None:
                        y_core = s["bbox"][1]
                        target_s = s
                    elif txt == "1.1" and y_nama is None:
                        y_nama = s["bbox"][1]

        has_field = y_core is not None
        if not has_field:
            doc.close()
            return {
                "file": str(pdf_path),
                "filename": pdf_path.name,
                "tipe": "JPL" if is_jpl else "OTB",
                "assets": assets,
                "asset_count": len(assets),
                "current_core": "-",
                "target_core": "-",
                "needs_correction": False,
                "has_field": False
            }

        # 2. Temukan entri TRA pada baris Nomor Aset
        table_tras = []
        if y_nomor_aset is not None:
            for b in blocks:
                if "lines" not in b: continue
                for l in b["lines"]:
                    for s in l["spans"]:
                        if abs(s["bbox"][1] - y_nomor_aset) < 8 and s["bbox"][0] > 300:
                            txt = s["text"].strip()
                            if "TRA" in txt:
                                table_tras.append((s["bbox"][0], txt))
            table_tras.sort(key=lambda x: x[0])

        # 3. Temukan nama OTB pada baris 1.1
        table_names = []
        if y_nama is not None:
            for b in blocks:
                if "lines" not in b: continue
                for l in b["lines"]:
                    for s in l["spans"]:
                        if abs(s["bbox"][1] - y_nama) < 8 and s["bbox"][0] > 300:
                            txt = s["text"].strip()
                            if txt and "Nama ODF" not in txt:
                                table_names.append((s["bbox"][0], txt))
            table_names.sort(key=lambda x: x[0])

        # 4. Tentukan jumlah kolom N
        num_cols = max(len(table_tras), len(table_names), len(assets), 1)

        # 5. Iterasi setiap kolom dan periksa nilai core
        columns = []
        has_any_mismatch = False

        for k in range(num_cols):
            M = num_cols - 1 - k
            col_x1 = GRID_RIGHT_BORDER - (M * GRID_COL_WIDTH)
            col_x0 = col_x1 - GRID_COL_WIDTH
            col_center = col_x1 - (GRID_COL_WIDTH / 2.0)

            # Cari TRA & Nama terkait kolom ini
            col_tra = ""
            for t_x, t_txt in table_tras:
                if col_x0 - 5 <= t_x <= col_x1 + 5:
                    col_tra = t_txt
                    break

            col_name = ""
            for n_x, n_txt in table_names:
                if col_x0 - 5 <= n_x <= col_x1 + 5:
                    col_name = n_txt
                    break

            if not col_tra and k < len(assets):
                # Fallback ke header asset
                col_tra = assets[k].split(":")[0].strip() if ":" in assets[k] else assets[k]
                if not col_name and ":" in assets[k]:
                    col_name = assets[k].split(":", 1)[1].strip()

            # Baca teks saat ini di baris Jumlah Core pada kolom ini
            curr_spans = []
            for b in blocks:
                if "lines" not in b: continue
                for l in b["lines"]:
                    for s in l["spans"]:
                        if abs(s["bbox"][1] - y_core) < 8 and (col_x0 - 2 <= s["bbox"][0] <= col_x1 + 2):
                            txt = s["text"].strip()
                            if txt and "Sesuai" not in txt and "ODF" not in txt and "Serat" not in txt:
                                curr_spans.append(txt)
            curr_text = " ".join(curr_spans).strip()

            target_val = get_target_core_for_asset(col_tra, col_name or pdf_path.stem, is_jpl=is_jpl)
            target_str = str(target_val)

            # Perlu koreksi jika nilai beda, kosong, atau masih menyertakan kata "Core"
            needs_col_corr = (curr_text != target_str)
            if needs_col_corr:
                has_any_mismatch = True

            columns.append({
                "col_index": k,
                "tra": col_tra,
                "name": col_name,
                "col_x0": round(col_x0, 2),
                "col_x1": round(col_x1, 2),
                "center_x": round(col_center, 2),
                "current": curr_text,
                "target": target_str,
                "needs_correction": needs_col_corr
            })

        doc.close()

        # Format ringkasan untuk Web UI
        if num_cols == 1:
            curr_summary = columns[0]["current"] or "-"
            target_summary = columns[0]["target"]
            tipe_label = "JPL" if is_jpl else "OTB (1 Kolom)"
        else:
            curr_summary = ", ".join(c["current"] or "-" for c in columns)
            target_summary = ", ".join(c["target"] for c in columns)
            tipe_label = f"OTB ({num_cols} Kolom)"

        return {
            "file": str(pdf_path),
            "filename": pdf_path.name,
            "tipe": tipe_label,
            "assets": assets,
            "asset_count": len(assets),
            "num_cols": num_cols,
            "columns": columns,
            "current_core": curr_summary,
            "target_core": target_summary,
            "needs_correction": has_any_mismatch,
            "has_field": True
        }
    except Exception as e:
        return {
            "file": str(pdf_path),
            "filename": pdf_path.name,
            "error": str(e),
            "needs_correction": False
        }


def apply_core_correction(pdf_path: Path, target_core=None, make_backup: bool = True, **kwargs) -> tuple[bool, str]:
    """Terapkan perbaikan nilai Jumlah Core secara presisi per kolom.
    Mendukung signature baru `(pdf_path, make_backup=True)` dan legacy `(pdf_path, target_core, make_backup=False)`.
    """
    if isinstance(target_core, bool):
        make_backup = target_core
        target_core = None
    elif "make_backup" in kwargs:
        make_backup = kwargs["make_backup"]
    ensure_font()
    if not pdf_path.exists():
        return False, "File tidak ditemukan"

    info = get_core_info(pdf_path)
    if not info or not info.get("has_field"):
        return False, "Baris 'Jumlah Core' tidak ditemukan di Halaman 1"

    if not info.get("needs_correction"):
        return True, "Nilai core sudah sesuai standar"

    try:
        # 1. Backup jika diminta
        if make_backup:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            b_dir = BACKUP_DIR / f"serat_optik_cores_{ts}"
            b_dir.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(str(pdf_path), str(b_dir / pdf_path.name))

        doc = fitz.open(str(pdf_path))
        page = doc[0]

        # Cari koordinat vertikal baris Jumlah Core
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
            return False, "Gagal melacak bounding box 'Jumlah Core'"

        row_y0 = target_s["bbox"][1]
        row_y1 = target_s["bbox"][3]
        row_origin_y = target_s["origin"][1]

        # Cari baseline Y dari teks angka yang sudah ada di baris 1.2 agar sejajar rata sempurna dengan tetangganya
        neighbor_y = None
        for b in blocks:
            if "lines" not in b: continue
            for l in b["lines"]:
                for s in l["spans"]:
                    if abs(s["bbox"][1] - row_y0) < 12 and s["bbox"][0] > 320:
                        txt = s["text"].strip()
                        if any(c.isdigit() for c in txt):
                            neighbor_y = s["origin"][1]
                            break
                if neighbor_y: break
            if neighbor_y: break

        y_baseline_use = neighbor_y if neighbor_y is not None else row_origin_y

        # 2. Tambahkan redaksi untuk seluruh kolom yang mismatch
        cols_to_fix = [c for c in info.get("columns", []) if c.get("needs_correction")]

        for col in cols_to_fix:
            col_x0 = col["col_x0"]
            col_x1 = col["col_x1"]
            # Redaksi aman: berjarak aman 1.5 pt dari garis batas agar garis tabel 100% utuh
            redact_rect = fitz.Rect(col_x0 + 1.5, row_y0 - 2.5, col_x1 - 1.5, row_y1 + 2.5)
            page.add_redact_annot(redact_rect, fill=(1, 1, 1))

        # Terapkan redaksi secara batch
        page.apply_redactions()

        # 3. Masukkan font DejaVuSans SETELAH redaksi selesai (mencegah invalidasi font oleh PyMuPDF)
        font_name_use = "helv"
        custom_font = None
        if FONT_PATH.exists():
            custom_font = fitz.Font(fontfile=str(FONT_PATH))
            page.insert_font(fontname="dejavu_core", fontfile=str(FONT_PATH))
            font_name_use = "dejavu_core"

        # 4. Tuliskan teks target pada kolom yang diperbaiki rata sempurna dengan tetangganya
        num_cols = info.get("num_cols", 1)
        for col in cols_to_fix:
            k = col["col_index"]
            M = num_cols - 1 - k
            target_text = col["target"]

            # Koordinat X standar rata presisi dengan aset tetangga (537.14 pt dikurangi pergeseran kolom)
            std_x = 537.14 - (M * 48.61)

            if custom_font:
                text_w = custom_font.text_length(target_text, fontsize=FONT_SIZE)
                std_w = custom_font.text_length("24", fontsize=FONT_SIZE)
            else:
                text_w = fitz.get_text_length(target_text, fontname="helv", fontsize=FONT_SIZE)
                std_w = fitz.get_text_length("24", fontname="helv", fontsize=FONT_SIZE)

            # Rata kiri-kanan presisi mengikuti posisi teks tetangga
            x_origin = std_x + ((std_w - text_w) / 2.0)
            page.insert_text((x_origin, y_baseline_use), target_text, fontname=font_name_use, fontsize=FONT_SIZE, color=(0, 0, 0))

        # 3. Simpan ke berkas sementara lalu timpa berkas asli
        temp_path = pdf_path.with_name(f"{pdf_path.stem}_tmp_{os.getpid()}.pdf")
        doc.save(str(temp_path), garbage=3, deflate=True)
        doc.close()
        shutil.move(str(temp_path), str(pdf_path))
        return True, f"Berhasil mengoreksi {len(cols_to_fix)} kolom"
    except Exception as e:
        return False, f"Error: {str(e)}"


def scan_folder(folder_path: Path) -> list[dict]:
    """Pindai seluruh berkas Serat Optik di folder secara kilat."""
    if not folder_path.exists():
        return []

    results = []
    for p in sorted(folder_path.rglob("*.pdf")):
        if any(part.lower() in ("backups", "backup") for part in p.relative_to(folder_path).parts[:-1]):
            continue
        if is_serat_optik_file(p):
            info = get_core_info(p)
            if info:
                try:
                    rel_dir = str(p.parent.relative_to(APP_DIR))
                except Exception:
                    rel_dir = str(p.parent)
                info["folder"] = rel_dir
                results.append(info)
    return results


def main():
    parser = argparse.ArgumentParser(description="Koreksi Jumlah Core Serat Optik (Multi-Kolom & Single-Kolom)")
    parser.add_argument("--folders", nargs="+", help="Folder-folder yang ingin dipindai/dikoreksi")
    parser.add_argument("--file", type=str, help="Satu file PDF spesifik")
    parser.add_argument("--scan", action="store_true", help="Hanya pindai dan tampilkan hasil tanpa mengubah file")
    parser.add_argument("--apply", action="store_true", help="Terapkan perbaikan nilai core")
    parser.add_argument("--no-backup", action="store_true", help="Jangan buat backup sebelum apply")
    parser.add_argument("--json", action="store_true", help="Keluarkan output dalam format JSON")
    args = parser.parse_args()

    ensure_font()
    load_database()

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
        for def_fld in ["05_pdf_merged", "01_pdf_source", "02_pdf_target"]:
            p = APP_DIR / def_fld
            if p.exists():
                for pf in sorted(p.rglob("*.pdf")):
                    if is_serat_optik_file(pf):
                        target_files.append(pf)

    target_files = sorted(list(set(target_files)))

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
                ok, msg = apply_core_correction(pdf_p, make_backup=not args.no_backup)
                item["applied"] = ok
                item["message"] = msg
                if ok:
                    applied_count += 1
                    # Refresh target core display
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
            print(f"  ├── Core   : Saat ini=[{it.get('current_core')}] -> Target=[{it.get('target_core')}]")
            print(f"  └── Status : {status_str}")


if __name__ == "__main__":
    main()
