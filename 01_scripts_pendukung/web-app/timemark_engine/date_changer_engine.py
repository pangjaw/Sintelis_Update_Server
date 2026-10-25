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
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)
try:
    import pymupdf as fitz
except ImportError:
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

ENGINE_DIR = Path(__file__).resolve().parent


def _get_date_font():
    """Mencari berkas font DejaVuSans-Bold.ttf asli agar identik 100% dengan dokumen P3STE."""
    candidates = [
        getattr(sys, "_MEIPASS", "") and Path(sys._MEIPASS) / "timemark_engine" / "DejaVuSans-Bold.ttf",
        getattr(sys, "_MEIPASS", "") and Path(sys._MEIPASS) / "config" / "DejaVuSans-Bold.ttf",
        getattr(sys, "_MEIPASS", "") and Path(sys._MEIPASS) / "DejaVuSans-Bold.ttf",
        ENGINE_DIR / "DejaVuSans-Bold.ttf",
        ENGINE_DIR / "config" / "DejaVuSans-Bold.ttf",
        ENGINE_DIR.parent / "config" / "DejaVuSans-Bold.ttf",
        Path("config/DejaVuSans-Bold.ttf"),
        Path("timemark_engine/DejaVuSans-Bold.ttf"),
        Path("DejaVuSans-Bold.ttf")
    ]
    for cand in candidates:
        if cand and Path(cand).is_file():
            return "DejaVuSans-Bold", str(Path(cand).resolve())
    return "Helvetica-Bold", None


def _init_pytesseract():
    """Menginisialisasi modul pytesseract dengan path biner tesseract yang tersedia."""
    try:
        import pytesseract
        tesseract_candidates = [
            os.environ.get("TESSERACT_CMD"),
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        ]
        tesseract_bin = next((c for c in tesseract_candidates if c and os.path.isfile(c)), None)
        if not tesseract_bin:
            tesseract_bin = shutil.which("tesseract")
        if tesseract_bin:
            pytesseract.pytesseract.tesseract_cmd = str(tesseract_bin)
        return pytesseract
    except Exception:
        return None


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

        # 1. Cek Halaman 1 (Vektor)
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

        # Fallback OCR Halaman 1 jika berkas adalah citra raster / Microsoft Print to PDF
        if not info["has_p1_date"] and len(doc) > 0:
            pytess = _init_pytesseract()
            if pytess:
                try:
                    from PIL import Image
                    p1 = doc[0]
                    clip_rect = fitz.Rect(0, 100, p1.rect.width, min(350, p1.rect.height))
                    pix = p1.get_pixmap(dpi=150, clip=clip_rect)
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    data = pytess.image_to_data(img, output_type=pytess.Output.DICT)
                    for i in range(len(data["text"])):
                        w = data["text"][i].strip()
                        if re.fullmatch(r"\d{4}[-/.]\d{2}[-/.]\d{2}", w) or re.fullmatch(r"\d{2}[-/.]\d{2}[-/.]\d{4}", w):
                            d_obj = parse_date_flexible(w)
                            if d_obj:
                                info["has_p1_date"] = True
                                if not info["detected_date"]:
                                    info["detected_date"] = d_obj.strftime("%Y-%m-%d")
                                    info["detected_date_dmy"] = d_obj.strftime("%d-%m-%Y")
                                break
                except Exception as ex:
                    print(f"[WARN] OCR scan_pdf_date P1 fallback error: {ex}")

        # 2. Cek Halaman Foto (Vektor)
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

        # Fallback OCR Halaman Foto jika berkas citra raster / Microsoft Print to PDF
        if not info["has_photo_date"] and len(doc) > 1:
            pytess = _init_pytesseract()
            if pytess:
                try:
                    from PIL import Image
                    for p_idx in range(1, len(doc)):
                        page = doc[p_idx]
                        clip_rect = fitz.Rect(0, 0, page.rect.width, min(250, page.rect.height))
                        pix = page.get_pixmap(dpi=150, clip=clip_rect)
                        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                        data = pytess.image_to_data(img, output_type=pytess.Output.DICT)
                        full_txt = " ".join(data["text"]).upper()
                        if "FOTO" in full_txt and "DOKUMENTASI" in full_txt:
                            for i in range(len(data["text"])):
                                w = data["text"][i].strip()
                                m = re.search(
                                    r"\b(Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember)\b",
                                    w,
                                    re.IGNORECASE
                                )
                                if m:
                                    info["has_photo_date"] = True
                                    if not info["detected_date"]:
                                        line_idx = data["line_num"][i]
                                        block_idx = data["block_num"][i]
                                        line_words = [
                                            data["text"][j].strip() for j in range(len(data["text"]))
                                            if data["block_num"][j] == block_idx and data["line_num"][j] == line_idx
                                        ]
                                        line_str = " ".join(line_words)
                                        d_obj = parse_date_flexible(line_str)
                                        if d_obj:
                                            info["detected_date"] = d_obj.strftime("%Y-%m-%d")
                                            info["detected_date_dmy"] = d_obj.strftime("%d-%m-%Y")
                                    break
                        if info["has_photo_date"]:
                            break
                except Exception as ex:
                    print(f"[WARN] OCR scan_pdf_date Photo fallback error: {ex}")

        doc.close()
    except Exception as e:
        info["status"] = "error"
        info["error"] = str(e)

    return info


def _get_date_cell_bounds(page, date_rect):
    """
    Mencari batas sel tabel tanggal (x_left, x_right) untuk penempatan teks rata tengah (centered).
    Memeriksa garis vektor drawing terlebih dahulu, kemudian fallback ke analisis densitas piksel raster.
    """
    scale = 150.0 / 72.0
    x_left = None
    x_right = None

    # 1. Coba deteksi dari vektor drawings jika tersedia
    try:
        drawings = page.get_drawings()
        v_lines = []
        for d in drawings:
            r = d.get("rect")
            if r and r.width < 3.0 and r.height > 10.0:
                if abs((r.y0 + r.y1) / 2.0 - (date_rect.y0 + date_rect.y1) / 2.0) < 20.0:
                    v_lines.append(r.x0)

        if v_lines:
            left_v = [x for x in v_lines if x < date_rect.x0]
            right_v = [x for x in v_lines if x > date_rect.x1]
            if left_v:
                x_left = max(left_v)
            if right_v:
                x_right = min(right_v)
    except Exception:
        pass

    # 2. Fallback: deteksi batas sel dari piksel citra raster (scanned / Microsoft Print to PDF)
    if x_left is None or x_right is None:
        try:
            import numpy as np
            from PIL import Image
            clip = fitz.Rect(
                max(0, date_rect.x0 - 25),
                max(0, date_rect.y0 - 15),
                min(page.rect.width, date_rect.x1 + 30),
                min(page.rect.height, date_rect.y1 + 15)
            )
            pix = page.get_pixmap(dpi=150, clip=clip)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            arr = np.array(img)
            gray = np.mean(arr, axis=2) if len(arr.shape) == 3 else arr
            dark_cols = np.sum(gray < 128, axis=0)
            h = gray.shape[0]

            # Cari garis vertikal di sebelah kiri teks
            mid_local_px = int((date_rect.x0 - clip.x0) * scale)
            left_lines = [c for c in range(mid_local_px) if dark_cols[c] > h * 0.45]
            if left_lines:
                x_left = clip.x0 + (max(left_lines) / scale)

            # Cari garis vertikal di sebelah kanan teks
            right_local_px = int((date_rect.x1 - clip.x0) * scale)
            right_lines = [c for c in range(right_local_px, len(dark_cols)) if dark_cols[c] > h * 0.45]
            if right_lines:
                x_right = clip.x0 + (min(right_lines) / scale)
        except Exception as e:
            print(f"[WARN] _get_date_cell_bounds raster fallback error: {e}")

    # Fallback default jika tidak ada garis terdeteksi
    if x_left is None:
        x_left = date_rect.x0 - 3.5
    if x_right is None:
        x_right = date_rect.x1 + 3.5

    return x_left, x_right


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
                x_left, x_right = _get_date_cell_bounds(p1, bbox)
                font_name, font_file = _get_date_font()
                font_size = target_p1_span.get("size", 7.2)

                # Hitung lebar teks untuk penempatan tepat di tengah (centered) sel tabel
                if font_file:
                    try:
                        custom_font = fitz.Font(fontfile=font_file)
                        text_w = custom_font.text_length(iso_date, fontsize=font_size)
                    except Exception:
                        text_w = fitz.get_text_length(iso_date, fontname="hebo", fontsize=font_size)
                else:
                    text_w = fitz.get_text_length(iso_date, fontname="hebo", fontsize=font_size)

                center_x = (x_left + x_right) / 2.0
                insert_x = center_x - (text_w / 2.0)
                origin = target_p1_span.get("origin")
                origin_y = origin[1] if origin else (bbox.y1 - 1.5)
                insert_pos = (insert_x, origin_y)

                # Redact HANYA di area teks dengan padding rapat 0.8pt (identik standar TCPDF P3STE asli),
                # JANGAN melebar ke garis batas sel tabel (x_left / x_right).
                clean_x0 = min(bbox.x0, insert_x) - 0.8
                clean_x1 = max(bbox.x1, insert_x + text_w) + 0.8
                clean_rect = fitz.Rect(clean_x0, bbox.y0 - 0.8, clean_x1, bbox.y1 + 0.8)
                p1.add_redact_annot(clean_rect, fill=(1, 1, 1))
                p1.apply_redactions()

                insert_kwargs = {
                    "fontsize": font_size,
                    "fontname": font_name,
                    "color": (0, 0, 0)
                }
                if font_file:
                    insert_kwargs["fontfile"] = font_file

                p1.insert_text(insert_pos, iso_date, **insert_kwargs)
                res["p1_modified"] = True
            else:
                # Fallback OCR Halaman 1 jika berkas citra raster / Microsoft Print to PDF
                pytess = _init_pytesseract()
                if pytess:
                    try:
                        from PIL import Image
                        scale = 72.0 / 150.0
                        clip_rect = fitz.Rect(0, 100, p1.rect.width, min(350, p1.rect.height))
                        pix = p1.get_pixmap(dpi=150, clip=clip_rect)
                        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                        data = pytess.image_to_data(img, output_type=pytess.Output.DICT)

                        ocr_date_box = None
                        for i in range(len(data["text"])):
                            w = data["text"][i].strip()
                            if re.fullmatch(r"\d{4}[-/.]\d{2}[-/.]\d{2}", w) or re.fullmatch(r"\d{2}[-/.]\d{2}[-/.]\d{4}", w):
                                x0 = data["left"][i] * scale
                                y0 = 100.0 + data["top"][i] * scale
                                w_pt = data["width"][i] * scale
                                h_pt = data["height"][i] * scale
                                ocr_date_box = fitz.Rect(x0, y0, x0 + w_pt, y0 + h_pt)
                                break

                        if ocr_date_box:
                            x_left, x_right = _get_date_cell_bounds(p1, ocr_date_box)
                            font_name, font_file = _get_date_font()
                            font_size = 7.2

                            if font_file:
                                try:
                                    custom_font = fitz.Font(fontfile=font_file)
                                    text_w = custom_font.text_length(iso_date, fontsize=font_size)
                                except Exception:
                                    text_w = fitz.get_text_length(iso_date, fontname="hebo", fontsize=font_size)
                            else:
                                text_w = fitz.get_text_length(iso_date, fontname="hebo", fontsize=font_size)

                            center_x = (x_left + x_right) / 2.0
                            insert_x = center_x - (text_w / 2.0)
                            insert_pos = (insert_x, ocr_date_box.y1 - 0.5)

                            clean_x0 = min(ocr_date_box.x0, insert_x) - 1.5
                            clean_x1 = max(ocr_date_box.x1, insert_x + text_w) + 1.5
                            clean_rect = fitz.Rect(clean_x0, ocr_date_box.y0 - 1.0, clean_x1, ocr_date_box.y1 + 1.0)
                            p1.add_redact_annot(clean_rect, fill=(1, 1, 1))
                            p1.apply_redactions()

                            insert_kwargs = {
                                "fontsize": font_size,
                                "fontname": font_name,
                                "color": (0, 0, 0)
                            }
                            if font_file:
                                insert_kwargs["fontfile"] = font_file

                            p1.insert_text(insert_pos, iso_date, **insert_kwargs)
                            res["p1_modified"] = True
                    except Exception as ex:
                        print(f"[WARN] OCR apply_date_change P1 error: {ex}")


        # ── MODIFIKASI HALAMAN FOTO (Header di bawah FOTO DOKUMENTASI) ──
        for p_idx in range(len(doc)):
            page = doc[p_idx]
            page_text = page.get_text()
            photo_span = None
            if "FOTO DOKUMENTASI" in page_text.upper():
                p_dict = page.get_text("dict")
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
                page_w = page.rect.width
                bbox = fitz.Rect(photo_span["bbox"])
                clean_rect = fitz.Rect(40, bbox.y0 - 1.0, page_w - 40, bbox.y1 + 1.0)
                page.add_redact_annot(clean_rect, fill=(1, 1, 1))
                page.apply_redactions()

                font_name, font_file = _get_date_font()
                font_size = photo_span.get("size", 7.2)
                origin = photo_span.get("origin")
                origin_y = origin[1] if origin else (bbox.y1 - 1.5)

                if font_file:
                    try:
                        custom_font = fitz.Font(fontfile=font_file)
                        text_w = custom_font.text_length(indo_date, fontsize=font_size)
                    except Exception:
                        text_w = fitz.get_text_length(indo_date, fontname="hebo", fontsize=font_size)
                else:
                    text_w = fitz.get_text_length(indo_date, fontname="hebo", fontsize=font_size)

                center_x = (page_w - text_w) / 2.0

                photo_kwargs = {
                    "fontsize": font_size,
                    "fontname": font_name,
                    "color": (0, 0, 0)
                }
                if font_file:
                    photo_kwargs["fontfile"] = font_file

                page.insert_text((center_x, origin_y), indo_date, **photo_kwargs)
                res["photo_modified"] = True
            elif p_idx >= 1:
                # Fallback OCR untuk citra raster / Microsoft Print to PDF
                pytess = _init_pytesseract()
                if pytess:
                    try:
                        from PIL import Image
                        page_w = page.rect.width
                        scale = 72.0 / 150.0
                        clip_rect = fitz.Rect(0, 0, page_w, min(250, page.rect.height))
                        pix = page.get_pixmap(dpi=150, clip=clip_rect)
                        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                        data = pytess.image_to_data(img, output_type=pytess.Output.DICT)
                        full_txt = " ".join(data["text"]).upper()
                        if "FOTO" in full_txt and "DOKUMENTASI" in full_txt:
                            month_idx = None
                            for i in range(len(data["text"])):
                                w = data["text"][i].strip()
                                if re.search(
                                    r"\b(Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember)\b",
                                    w,
                                    re.IGNORECASE
                                ):
                                    if data["top"][i] * scale < 200:
                                        month_idx = i
                                        break

                            if month_idx is not None:
                                target_line = data["line_num"][month_idx]
                                target_block = data["block_num"][month_idx]
                                line_boxes = [
                                    (
                                        data["left"][j] * scale,
                                        data["top"][j] * scale,
                                        (data["left"][j] + data["width"][j]) * scale,
                                        (data["top"][j] + data["height"][j]) * scale
                                    )
                                    for j in range(len(data["text"]))
                                    if data["block_num"][j] == target_block and data["line_num"][j] == target_line and data["text"][j].strip()
                                ]
                                if line_boxes:
                                    y0 = min(b[1] for b in line_boxes)
                                    y1 = max(b[3] for b in line_boxes)
                                    clean_rect = fitz.Rect(40.0, y0 - 2.0, page_w - 40.0, y1 + 2.0)
                                    page.add_redact_annot(clean_rect, fill=(1, 1, 1))
                                    page.apply_redactions()

                                    font_name, font_file = _get_date_font()
                                    font_size = 7.2
                                    origin_y = y1 - 0.5

                                    if font_file:
                                        try:
                                            custom_font = fitz.Font(fontfile=font_file)
                                            text_w = custom_font.text_length(indo_date, fontsize=font_size)
                                        except Exception:
                                            text_w = fitz.get_text_length(indo_date, fontname="hebo", fontsize=font_size)
                                    else:
                                        text_w = fitz.get_text_length(indo_date, fontname="hebo", fontsize=font_size)

                                    center_x = (page_w - text_w) / 2.0

                                    photo_kwargs = {
                                        "fontsize": font_size,
                                        "fontname": font_name,
                                        "color": (0, 0, 0)
                                    }
                                    if font_file:
                                        photo_kwargs["fontfile"] = font_file

                                    page.insert_text((center_x, origin_y), indo_date, **photo_kwargs)
                                    res["photo_modified"] = True
                    except Exception as ex:
                        print(f"[WARN] OCR apply_date_change Photo error on page {p_idx}: {ex}")

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
