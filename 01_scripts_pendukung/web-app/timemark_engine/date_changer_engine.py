"""
date_changer_engine.py — Engine untuk mengganti seluruh tanggal dalam berkas PDF & nama berkas.

Mendukung:
1. Penggantian nama file PDF (prefix DD-MM-YYYY_*, suffix *_DD-MM-YYYY.pdf, atau teks tanggal).
2. Penggantian tanggal pelaksanaan pada Formulir Halaman 1 (sel tabel Tanggal: YYYY-MM-DD).
3. Penggantian tanggal header lampiran Halaman Foto (di bawah FOTO DOKUMENTASI: DD Bulan YYYY, rata tengah).
4. Watermark kamera GPS pada citra foto 0%, 50%, 100% tetap dipertahankan asli tanpa modifikasi.
"""

import os
import re
import sys
import shutil
from datetime import datetime
from pathlib import Path
import fitz

INDONESIAN_MONTHS = [
    "", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember"
]

MONTH_MAP_ID = {
    "januari": 1, "jan": 1, "februari": 2, "feb": 2,
    "maret": 3, "mar": 3, "april": 4, "apr": 4,
    "mei": 5, "may": 5, "juni": 6, "jun": 6,
    "juli": 7, "jul": 7, "agustus": 8, "agt": 8, "aug": 8,
    "september": 9, "sep": 9, "oktober": 10, "okt": 10,
    "november": 11, "nov": 11, "desember": 12, "des": 12
}


def parse_date_flexible(date_str: str) -> datetime | None:
    """Mengurai string tanggal dalam berbagai format umum ke objek datetime."""
    if not date_str:
        return None
    date_str = str(date_str).strip()

    # 1. ISO YYYY-MM-DD
    m_iso = re.match(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})$", date_str)
    if m_iso:
        try:
            return datetime(int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3)))
        except ValueError:
            pass

    # 2. DMY DD-MM-YYYY
    m_dmy = re.match(r"^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})$", date_str)
    if m_dmy:
        try:
            return datetime(int(m_dmy.group(3)), int(m_dmy.group(2)), int(m_dmy.group(1)))
        except ValueError:
            pass

    # 3. Format Indonesia: "09 Februari 2025" atau "9 Feb 2025"
    m_idn = re.search(
        r"(\d{1,2})\s+(januari|februari|maret|april|mei|juni|juli|agustus|september|oktober|november|desember|jan|feb|mar|apr|jun|jul|agt|aug|sep|okt|nov|des)\s+(\d{4})",
        date_str,
        re.IGNORECASE
    )
    if m_idn:
        day = int(m_idn.group(1))
        m_name = m_idn.group(2).lower()
        month = MONTH_MAP_ID.get(m_name, 1)
        year = int(m_idn.group(3))
        try:
            return datetime(year, month, day)
        except ValueError:
            pass

    return None


def get_new_filename(orig_filename: str, new_date: datetime) -> str:
    """
    Menghasilkan nama berkas baru berdasarkan tanggal baru.
    Mengikuti pola deteksi dari P3-STE download & detector.js:
    - Prefix: '09-02-2025_PERAWATAN...pdf' -> '15-03-2026_PERAWATAN...pdf'
    - Suffix: 'PERAWATAN PTLS BOP 09-02-2025.pdf' -> 'PERAWATAN PTLS BOP 15-03-2026.pdf'
    - Format teks bulan: '... 09 Februari 2025.pdf' -> '... 15 Maret 2026.pdf'
    """
    dmy_dash = new_date.strftime("%d-%m-%Y")
    indo_str = f"{new_date.day:02d} {INDONESIAN_MONTHS[new_date.month]} {new_date.year}"

    name, ext = os.path.splitext(orig_filename)

    # 1. Cek pola prefix DD-MM-YYYY_
    m_pre = re.match(r"^(\d{2}-\d{2}-\d{4})(_.*)$", name, re.IGNORECASE)
    if m_pre:
        return f"{dmy_dash}{m_pre.group(2)}{ext}"

    # 2. Cek pola teks Indonesia dalam nama berkas (misal "09 FEBRUARI 2025")
    m_idn = re.search(
        r"\b\d{1,2}\s+(?:JANUARI|FEBRUARI|MARET|APRIL|MEI|JUNI|JULI|AGUSTUS|SEPTEMBER|OKTOBER|NOVEMBER|DESEMBER)\s+\d{4}\b",
        name,
        re.IGNORECASE
    )
    if m_idn:
        new_name = name[:m_idn.start()] + indo_str + name[m_idn.end():]
        return f"{new_name}{ext}"

    # 3. Cek pola suffix / embedded DD-MM-YYYY
    m_std = re.search(r"\b(\d{2})[-/.](\d{2})[-/.](\d{4})\b", name)
    if m_std:
        new_name = name[:m_std.start()] + dmy_dash + name[m_std.end():]
        return f"{new_name}{ext}"

    # Fallback: tambahkan tanggal di akhir nama jika tidak ada pola tanggal
    return f"{name}_{dmy_dash}{ext}"


def scan_pdf_date(pdf_path: str) -> dict:
    """
    Memindai berkas PDF untuk mengekstrak informasi tanggal saat ini:
    - Tanggal pada nama berkas
    - Tanggal pada Halaman 1 (sel Tanggal)
    - Tanggal pada Halaman Foto (header FOTO DOKUMENTASI)
    """
    info = {
        "path": os.path.normpath(pdf_path),
        "filename": os.path.basename(pdf_path),
        "detected_date": None,         # Format YYYY-MM-DD
        "detected_date_dmy": None,     # Format DD-MM-YYYY
        "has_p1_date": False,
        "has_photo_date": False,
        "page_count": 0,
        "status": "ready",
        "error": None
    }

    if not os.path.isfile(pdf_path):
        info["status"] = "error"
        info["error"] = "Berkas tidak ditemukan"
        return info

    try:
        # Coba deteksi dari nama berkas terlebih dahulu
        fn_date = parse_date_flexible(info["filename"])
        if fn_date:
            info["detected_date"] = fn_date.strftime("%Y-%m-%d")
            info["detected_date_dmy"] = fn_date.strftime("%d-%m-%Y")

        doc = fitz.open(pdf_path)
        info["page_count"] = len(doc)

        # 1. Cek Halaman 1
        if len(doc) > 0:
            p1 = doc[0]
            p1_dict = p1.get_text("dict")
            for b in p1_dict.get("blocks", []):
                for l in b.get("lines", []):
                    for s in l.get("spans", []):
                        txt = s.get("text", "").strip()
                        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", txt) or re.fullmatch(r"\d{2}-\d{2}-\d{4}", txt):
                            info["has_p1_date"] = True
                            if not info["detected_date"]:
                                d_obj = parse_date_flexible(txt)
                                if d_obj:
                                    info["detected_date"] = d_obj.strftime("%Y-%m-%d")
                                    info["detected_date_dmy"] = d_obj.strftime("%d-%m-%Y")
                            break

        # 2. Cek Halaman Foto (mencari halaman dengan teks 'FOTO DOKUMENTASI')
        for p_idx in range(len(doc)):
            page = doc[p_idx]
            txt_full = page.get_text()
            if "FOTO DOKUMENTASI" in txt_full.upper():
                p_dict = page.get_text("dict")
                for b in p_dict.get("blocks", []):
                    for l in b.get("lines", []):
                        for s in l.get("spans", []):
                            txt = s.get("text", "").strip()
                            if re.search(
                                r"\b\d{1,2}\s+(Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember)\s+\d{4}\b",
                                txt,
                                re.IGNORECASE
                            ):
                                info["has_photo_date"] = True
                                if not info["detected_date"]:
                                    d_obj = parse_date_flexible(txt)
                                    if d_obj:
                                        info["detected_date"] = d_obj.strftime("%Y-%m-%d")
                                        info["detected_date_dmy"] = d_obj.strftime("%d-%m-%Y")
                                break

        doc.close()
    except Exception as e:
        info["status"] = "error"
        info["error"] = str(e)

    return info


def apply_date_change(pdf_path: str, new_date_str: str, create_backup: bool = False) -> dict:
    """
    Menerapkan perubahan tanggal pada berkas PDF secara in-place:
    1. Memperbarui tanggal formulir Halaman 1 (YYYY-MM-DD) via PyMuPDF redactions.
    2. Memperbarui tanggal header foto (DD Bulan YYYY, rata tengah) via PyMuPDF redactions.
    3. Opsional membuat salinan cadangan (.bak).
    4. Mengganti nama berkas PDF ke nama baru berbasis tanggal baru.
    """
    res = {
        "ok": False,
        "old_path": os.path.normpath(pdf_path),
        "new_path": os.path.normpath(pdf_path),
        "old_name": os.path.basename(pdf_path),
        "new_name": os.path.basename(pdf_path),
        "p1_modified": False,
        "photo_modified": False,
        "error": None
    }

    if not os.path.isfile(pdf_path):
        res["error"] = "Berkas tidak ditemukan"
        return res

    new_date = parse_date_flexible(new_date_str)
    if not new_date:
        res["error"] = f"Format tanggal baru tidak valid: {new_date_str}"
        return res

    iso_date = new_date.strftime("%Y-%m-%d")
    indo_date = f"{new_date.day:02d} {INDONESIAN_MONTHS[new_date.month]} {new_date.year}"
    target_filename = get_new_filename(res["old_name"], new_date)
    res["new_name"] = target_filename

    parent_dir = os.path.dirname(pdf_path)
    final_pdf_path = os.path.join(parent_dir, target_filename)
    res["new_path"] = os.path.normpath(final_pdf_path)

    # 1. Cadangkan berkas jika diminta
    if create_backup:
        backup_path = pdf_path + ".bak"
        try:
            shutil.copy2(pdf_path, backup_path)
            res["backup_path"] = backup_path
        except Exception as e:
            print(f"[WARN] Gagal membuat backup: {e}")

    temp_out_path = os.path.join(parent_dir, f"_temp_dt_{os.getpid()}_{os.path.basename(pdf_path)}")

    try:
        doc = fitz.open(pdf_path)

        # ── MODIFIKASI HALAMAN 1 (Formulir Pemeriksaan) ──
        if len(doc) > 0:
            p1 = doc[0]
            p1_dict = p1.get_text("dict")
            target_p1_span = None
            for b in p1_dict.get("blocks", []):
                for l in b.get("lines", []):
                    for s in l.get("spans", []):
                        txt = s.get("text", "").strip()
                        # Tanggal pada Halaman 1: YYYY-MM-DD atau DD-MM-YYYY
                        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", txt) or re.fullmatch(r"\d{2}-\d{2}-\d{4}", txt):
                            target_p1_span = s
                            break
                    if target_p1_span:
                        break
                if target_p1_span:
                    break

            if target_p1_span:
                bbox = fitz.Rect(target_p1_span["bbox"])
                clean_rect = fitz.Rect(bbox.x0 - 0.5, bbox.y0 - 0.5, bbox.x1 + 0.5, bbox.y1 + 0.5)
                p1.add_redact_annot(clean_rect, fill=(1, 1, 1))
                p1.apply_redactions()

                # Sisipkan teks tanggal baru (ISO: YYYY-MM-DD)
                font_size = target_p1_span.get("size", 7.8)
                p1.insert_text(
                    (bbox.x0, bbox.y1 - 1.5),
                    iso_date,
                    fontname="Helvetica-Bold",
                    fontsize=font_size,
                    color=(0, 0, 0)
                )
                res["p1_modified"] = True

        # ── MODIFIKASI HALAMAN FOTO (Header di bawah FOTO DOKUMENTASI) ──
        for p_idx in range(len(doc)):
            page = doc[p_idx]
            page_text = page.get_text()
            if "FOTO DOKUMENTASI" in page_text.upper():
                p_dict = page.get_text("dict")
                page_w = page.rect.width
                photo_span = None
                for b in p_dict.get("blocks", []):
                    for l in b.get("lines", []):
                        for s in l.get("spans", []):
                            txt = s.get("text", "").strip()
                            m = re.search(
                                r"\b\d{1,2}\s+(Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember)\s+\d{4}\b",
                                txt,
                                re.IGNORECASE
                            )
                            if m:
                                photo_span = s
                                break
                        if photo_span:
                            break
                    if photo_span:
                        break

                if photo_span:
                    bbox = fitz.Rect(photo_span["bbox"])
                    clean_rect = fitz.Rect(40, bbox.y0 - 1.0, page_w - 40, bbox.y1 + 1.0)
                    page.add_redact_annot(clean_rect, fill=(1, 1, 1))
                    page.apply_redactions()

                    # Hitung posisi X tengah persis
                    font_size = photo_span.get("size", 7.2)
                    text_w = fitz.get_text_length(indo_date, fontname="Helvetica-Bold", fontsize=font_size)
                    center_x = (page_w - text_w) / 2.0

                    page.insert_text(
                        (center_x, bbox.y1 - 1.5),
                        indo_date,
                        fontname="Helvetica-Bold",
                        fontsize=font_size,
                        color=(0, 0, 0)
                    )
                    res["photo_modified"] = True

        # Simpan ke temp file
        doc.save(temp_out_path, deflate=True)
        doc.close()

        # Ganti file asli
        if os.path.exists(temp_out_path):
            if os.path.normpath(pdf_path) == os.path.normpath(final_pdf_path):
                # Nama file sama
                os.replace(temp_out_path, pdf_path)
            else:
                # Rename ke nama berkas baru
                if os.path.isfile(final_pdf_path) and os.path.normpath(final_pdf_path) != os.path.normpath(pdf_path):
                    try:
                        os.remove(final_pdf_path)
                    except Exception:
                        pass
                os.replace(temp_out_path, final_pdf_path)
                if os.path.isfile(pdf_path) and os.path.normpath(pdf_path) != os.path.normpath(final_pdf_path):
                    try:
                        os.remove(pdf_path)
                    except Exception:
                        pass

        res["ok"] = True
    except Exception as e:
        res["error"] = str(e)
        if os.path.exists(temp_out_path):
            try:
                os.remove(temp_out_path)
            except Exception:
                pass

    return res
