"""
personnel_changer_engine.py — Engine untuk memindai dan mengganti personil & nomor SC pada berkas PDF.

Mendukung:
1. Pemindaian akurat berkas PDF (ekstraksi tanggal & personil saat ini pada Halaman 1).
2. Penerapan personil baru (Nama & No. SC) secara in-place overwrite.
3. Penanganan otomatis tata letak formulir:
   - Tata letak Standar 1-Kolom (Wesel, Sinyal, CTC-CTS, Catu Daya, Pintu Perlintasan, Serat Optik, dll.)
   - Tata letak Siemens 2-Kolom (Axle Counter ZP Siemens, Wesel Siemens)
4. Penataan urutan dinamis baris personil di lembar formulir Halaman 1.
"""

import os
import re
import sys
import shutil
from pathlib import Path
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)
try:
    import pymupdf as fitz
except ImportError:
    import fitz

# Pastikan timemark_engine ada di sys.path
ENGINE_DIR = Path(__file__).resolve().parent
if str(ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(ENGINE_DIR))

try:
    from employee_manager import load_pegawai_config, replace_page1_employee_names, detect_raster_table_lines
except ImportError:
    load_pegawai_config = None
    replace_page1_employee_names = None
    detect_raster_table_lines = None

try:
    from audit_and_correct_personnel import extract_personnel_from_pdf, get_roster_sets
except ImportError:
    extract_personnel_from_pdf = None
    get_roster_sets = None


def _extract_ocr_words(page: fitz.Page) -> list:
    """Fallback OCR word extractor for scanned or Print-to-PDF pages lacking digital text."""
    try:
        import pytesseract
        from PIL import Image

        tesseract_candidates = [
            os.environ.get("TESSERACT_CMD"),
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        ]
        tesseract_bin = next((c for c in tesseract_candidates if c and os.path.isfile(c)), None)
        if not tesseract_bin:
            import shutil
            tesseract_bin = shutil.which("tesseract")
        if tesseract_bin:
            pytesseract.pytesseract.tesseract_cmd = str(tesseract_bin)

        pix = page.get_pixmap(dpi=200)
        scale = 72.0 / 200.0
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        y_top_px = int(160.0 / scale)
        y_bot_px = int(min(300.0, page.rect.height) / scale)
        crop_img = img.crop((0, y_top_px, img.width, y_bot_px))

        data = pytesseract.image_to_data(crop_img, output_type=pytesseract.Output.DICT)
        words = []
        for i in range(len(data["text"])):
            t = data["text"][i].strip()
            if not t:
                continue
            x0 = data["left"][i] * scale
            y0 = 160.0 + data["top"][i] * scale
            x1 = x0 + data["width"][i] * scale
            y1 = y0 + data["height"][i] * scale
            # (x0, y0, x1, y1, word, block_no, line_no, word_no)
            words.append((x0, y0, x1, y1, t, data["block_num"][i], data["line_num"][i], data["word_num"][i]))
        return words
    except Exception:
        return []


def _get_page1_font(doc: fitz.Document = None):
    """Mencari font tebal yang cocok untuk penulisan personil."""
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
    font_file = None
    for cand in candidates:
        if cand and Path(cand).is_file():
            font_file = str(Path(cand).resolve())
            break

    if font_file:
        try:
            return "DejaVuSans-Bold", font_file
        except Exception:
            pass
    return "DejaVuSans-Bold", None


def extract_personnel_from_layout(page: fitz.Page) -> list[str]:
    """
    Mengekstrak nama-nama personil pelaksana dari Halaman 1 berdasarkan koordinat sel fisik
    sehingga mendukung baik personil dalam daftar profil maupun personil kustom/manual.
    """
    words = page.get_text("words", sort=True)
    if not words or not any("DILAKSANAKAN" in w[4].upper() for w in words):
        ocr_words = _extract_ocr_words(page)
        if ocr_words:
            words = ocr_words

    if not words:
        return []

    # Cek apakah tata letak 2-Kolom (Siemens)
    is_siemens = False
    for w in words:
        if "DILAKSANAKAN" in w[4].upper() and w[0] > 350 and 150 <= w[1] <= 260:
            is_siemens = True
            break

    names = []
    stop_kw = {"DILAKSANAKAN", "OLEH", "OLEH:", "NO.", "SC", "NO.SC", "PRP", "NIPP", "LOKASI", "TANGGAL"}

    if is_siemens:
        # Kolom Kiri (KAUR): x in [245, 370], y in [180, 225]
        left_words = [w for w in words if 245 <= w[0] <= 370 and 180 <= w[1] <= 225]
        # Kolom Kanan (PNC): x in [460, 565], y in [175, 230]
        right_words = [w for w in words if 460 <= w[0] <= 565 and 175 <= w[1] <= 230]

        def _group_by_y(w_list):
            lines = []
            for w in sorted(w_list, key=lambda x: (round(x[1], -1), x[0])):
                if not lines or abs(w[1] - lines[-1][0][1]) > 5:
                    lines.append([w])
                else:
                    lines[-1].append(w)
            res = []
            for l in lines:
                text = " ".join(x[4] for x in sorted(l, key=lambda x: x[0])).strip(" :;,.-")
                if text and not any(kw == text.upper() or text.upper().startswith(kw + " ") for kw in stop_kw):
                    if len(text) >= 3 and not re.match(r"^(PRP|NIPP)\b", text, re.I):
                        res.append(text)
            return res

        names.extend(_group_by_y(left_words))
        names.extend(_group_by_y(right_words))
    else:
        # Standar 1-Kolom: cari posisi baris DILAKSANAKAN
        dila_w = next((w for w in words if "DILAKSANAKAN" in w[4].upper() or "DILAKS" in w[4].upper()), None)
        y_dila = (dila_w[1] + dila_w[3]) / 2 if dila_w else 210.0
        mid_words = [w for w in words if 250 <= w[0] <= 380 and (y_dila - 22.0 <= (w[1] + w[3]) / 2 <= y_dila + 28.0)]
        lines = []
        for w in sorted(mid_words, key=lambda x: (round(x[1], -1), x[0])):
            if not lines or abs(w[1] - lines[-1][0][1]) > 5:
                lines.append([w])
            else:
                lines[-1].append(w)
        for l in lines:
            text = " ".join(x[4] for x in sorted(l, key=lambda x: x[0])).strip(" :;,.-")
            if text and not any(kw == text.upper() or text.upper().startswith(kw + " ") for kw in stop_kw):
                if len(text) >= 3 and not re.match(r"^(PRP|NIPP)\b", text, re.I):
                    names.append(text)

    return names


def scan_pdf_personnel(pdf_path: str) -> dict:
    """
    Memindai berkas PDF untuk mengekstrak informasi personil dan tanggal saat ini.
    """
    info = {
        "path": os.path.normpath(pdf_path),
        "filename": os.path.basename(pdf_path),
        "date": "-",
        "detected_personnel": [],
        "personnel_str": "-",
        "page_count": 0,
        "status": "ready",
        "error": None
    }

    if not os.path.isfile(pdf_path):
        info["status"] = "error"
        info["error"] = "Berkas tidak ditemukan"
        return info

    try:
        # Coba deteksi tanggal dari nama berkas
        m_date = re.search(r"\b(\d{2})[-/.](\d{2})[-/.](\d{4})\b", info["filename"])
        if m_date:
            info["date"] = f"{m_date.group(1)}-{m_date.group(2)}-{m_date.group(3)}"

        doc = fitz.open(pdf_path)
        info["page_count"] = len(doc)

        if len(doc) > 0:
            page = doc[0]
            # Ambil tanggal halaman 1 jika nama berkas tidak ada tanggal
            if info["date"] == "-":
                p1_text = page.get_text()
                m_p1 = re.search(r"\b(\d{4}-\d{2}-\d{2}|\d{2}-\d{2}-\d{4})\b", p1_text)
                if m_p1:
                    info["date"] = m_p1.group(1)

            # Ekstraksi personil menggunakan koordinat layout fisik
            detected = extract_personnel_from_layout(page)

            # Jika tidak terdeteksi dari layout fisik, gunakan parser audit berbasis teks
            if not detected and extract_personnel_from_pdf:
                cfg = load_pegawai_config() if load_pegawai_config else {}
                kaur_map, pnc_map, _ = get_roster_sets(cfg) if get_roster_sets else ({}, {}, {})
                found_k, found_p, raw_names = extract_personnel_from_pdf(doc, kaur_map, pnc_map)
                comb = []
                for k in found_k:
                    comb.append(k.get("nama", ""))
                for p in found_p:
                    comb.append(p.get("nama", ""))
                if not comb and raw_names:
                    comb = raw_names
                detected = [n for n in comb if n]

            info["detected_personnel"] = detected
            if detected:
                info["personnel_str"] = ", ".join(detected)

        doc.close()
    except Exception as e:
        info["status"] = "error"
        info["error"] = str(e)

    return info


def apply_personnel_change(pdf_path: str, employees: list[dict]) -> dict:
    """
    Menerapkan perubahan personil dan nomor SC baru pada berkas PDF secara in-place overwrite.
    Mendukung tata letak Siemens 2-kolom dan Standar 1-kolom.
    employees: list of dict [{"nama": "...", "no_sc": "..."}, ...]
    """
    res = {
        "ok": False,
        "path": os.path.normpath(pdf_path),
        "filename": os.path.basename(pdf_path),
        "error": None
    }

    if not os.path.isfile(pdf_path):
        res["error"] = "Berkas tidak ditemukan"
        return res

    # Bersihkan input personil
    clean_employees = []
    for emp in employees or []:
        nama = str(emp.get("nama", "")).strip().upper()
        no_sc = str(emp.get("no_sc", "")).strip().upper()
        if nama:
            clean_employees.append({
                "nama": nama,
                "no_sc": no_sc if no_sc else "-",
                "nipp": str(emp.get("nipp", "-")).strip()
            })

    if not clean_employees:
        res["error"] = "Tidak ada nama personil valid yang ditentukan"
        return res

    temp_path = pdf_path + f".tmp_{os.getpid()}"

    try:
        doc = fitz.open(pdf_path)
        if len(doc) == 0:
            doc.close()
            res["error"] = "Dokumen PDF kosong"
            return res

        page = doc[0]

        # Kumpulkan spans pada halaman 1
        spans = []
        for b in page.get_text("dict").get("blocks", []):
            if "lines" in b:
                for l in b["lines"]:
                    for s in l.get("spans", []):
                        if s.get("text", "").strip():
                            spans.append(s)

        # Cek apakah tata letak 2-Kolom Siemens
        right_dila = next((s for s in spans if "DILAKSANAKAN" in s["text"].upper() and s["bbox"][0] > 350 and 150 <= s["bbox"][1] <= 260), None)

        font_name, font_file = _get_page1_font(doc)
        custom_font = None
        if font_file and os.path.isfile(font_file):
            try:
                custom_font = fitz.Font(fontfile=font_file)
            except Exception:
                custom_font = None

        def _calc_w(txt: str, fsize: float) -> float:
            if custom_font:
                try:
                    return custom_font.text_length(txt, fontsize=fsize)
                except Exception:
                    pass
            try:
                return fitz.get_text_length(txt, fontname="hebo", fontsize=fsize)
            except Exception:
                return len(txt) * fsize * 0.55

        font_size_name = 7.8
        font_size_sc = 7.0

        insert_kwargs = {"fontsize": font_size_name, "color": (0, 0, 0), "fontname": font_name}
        if font_file:
            insert_kwargs["fontfile"] = font_file

        insert_sc_kwargs = {"fontsize": font_size_sc, "color": (0, 0, 0), "fontname": font_name}
        if font_file:
            insert_sc_kwargs["fontfile"] = font_file

        if right_dila:
            # === TATA LETAK SIEMENS 2-KOLOM (AXLE COUNTER / WESEL SIEMENS) ===
            left_dila = next((s for s in spans if "DILAKSANAKAN" in s["text"].upper() and s["bbox"][0] < 300 and 150 <= s["bbox"][1] <= 260), None)
            left_sc = next((s for s in spans if "NO. SC" in s["text"].upper() and s["bbox"][0] < 300 and s["bbox"][1] > 220), None)
            right_sc = next((s for s in spans if "NO. SC" in s["text"].upper() and s["bbox"][0] > 350 and s["bbox"][1] > 220), None)

            y_dila_l = (left_dila["bbox"][1] + left_dila["bbox"][3]) / 2 if left_dila else 198.7
            y_sc_l = (left_sc["bbox"][1] + left_sc["bbox"][3]) / 2 if left_sc else 262.0
            y_dila_r = (right_dila["bbox"][1] + right_dila["bbox"][3]) / 2
            y_sc_r = (right_sc["bbox"][1] + right_sc["bbox"][3]) / 2 if right_sc else 262.0

            # Redact sel kiri (KAUR) dan kanan (PNC) dengan margin aman di dalam sel
            page.add_redact_annot(fitz.Rect(249.0, 181.0, 369.0, 224.0), fill=(1, 1, 1))
            page.add_redact_annot(fitz.Rect(249.0, 241.0, 369.0, 284.0), fill=(1, 1, 1))
            page.add_redact_annot(fitz.Rect(463.0, 176.0, 564.0, 229.0), fill=(1, 1, 1))
            page.add_redact_annot(fitz.Rect(463.0, 236.0, 564.0, 284.0), fill=(1, 1, 1))
            page.apply_redactions()

            # Personil 1 -> Sel Kiri (KAUR)
            emp0 = clean_employees[0]
            n0 = emp0["nama"]
            sc0 = emp0["no_sc"]

            w_n0 = _calc_w(n0, font_size_name)
            x_n0 = 249.0 + (369.0 - 249.0 - w_n0) / 2
            page.insert_text((x_n0, y_dila_l + font_size_name * 0.35), n0, **insert_kwargs)

            w_sc0 = _calc_w(sc0, font_size_sc)
            x_sc0 = 249.0 + (369.0 - 249.0 - w_sc0) / 2
            page.insert_text((x_sc0, y_sc_l + font_size_sc * 0.35), sc0, **insert_sc_kwargs)

            # Personil 2..N -> Sel Kanan (PNC)
            pnc_emps = clean_employees[1:]
            m = len(pnc_emps)
            if m > 0:
                for idx, emp in enumerate(pnc_emps):
                    nm = emp["nama"]
                    sc = emp["no_sc"]
                    if m == 1:
                        y_nm = y_dila_r
                        y_sc = y_sc_r
                    elif m == 2:
                        y_nm = (y_dila_r - 9.0) + idx * 18.0
                        y_sc = (y_sc_r - 9.0) + idx * 18.0
                    elif m == 3:
                        y_nm = (y_dila_r - 15.5) + idx * 15.5
                        y_sc = (y_sc_r - 15.5) + idx * 15.5
                    else:
                        step = 44.0 / m
                        y_nm = (y_dila_r - 20.0) + (idx + 0.5) * step
                        y_sc = (y_sc_r - 20.0) + (idx + 0.5) * step

                    w_nm = _calc_w(nm, font_size_name)
                    x_nm = 463.0 + (564.0 - 463.0 - w_nm) / 2
                    page.insert_text((x_nm, y_nm + font_size_name * 0.35), nm, **insert_kwargs)

                    w_sc = _calc_w(sc, font_size_sc)
                    x_sc = 463.0 + (564.0 - 463.0 - w_sc) / 2
                    page.insert_text((x_sc, y_sc + font_size_sc * 0.35), sc, **insert_sc_kwargs)
        else:
            # === TATA LETAK STANDAR 1-KOLOM (WESEL, SINYAL, CTC-CTS, CATU DAYA, DLL.) ===
            # Prioritaskan pemanggilan replace_page1_employee_names dari employee_manager
            handled = False
            if replace_page1_employee_names:
                try:
                    handled = replace_page1_employee_names(doc, clean_employees, sc_only=False)
                except Exception as ex:
                    print(f"[WARN] replace_page1_employee_names failed: {ex}, fallback to internal drawing-based layout")
                    handled = False

            if not handled:
                # Fallback algoritma deteksi garis dinamis page.get_drawings()
                left_dila = next((s for s in spans if "DILAKSANAKAN" in s["text"].upper() and s["bbox"][0] < 300 and 150 <= s["bbox"][1] <= 260), None)
                sc_label = next((s for s in spans if any(k in s["text"].upper() for k in ["NO. SC", "NO.SC", "SC"]) and s["bbox"][0] > 350 and 150 <= s["bbox"][1] <= 260), None)
                if not left_dila:
                    left_dila = {"bbox": (196.6, 200.0, 250.1, 210.0), "text": "DILAKSANAKAN"}
                if not sc_label:
                    sc_label = {"bbox": (407.4, 205.0, 436.5, 215.0), "text": "NO. SC."}

                y_mid = (left_dila["bbox"][1] + left_dila["bbox"][3]) / 2
                drawings = page.get_drawings()
                h_lines = set()
                v_lines = set()
                for d in drawings:
                    r = d["rect"]
                    if r.width > 20 and r.height < 2 and (y_mid - 60 <= r.y0 <= y_mid + 60):
                        h_lines.add(round(r.y0, 2))
                    elif r.height > 20 and r.width < 2 and (y_mid - 60 <= (r.y0 + r.y1) / 2 <= y_mid + 60):
                        v_lines.add(round(r.x0, 2))

                is_raster_table = False
                if (len(h_lines) < 2 or len(v_lines) < 2) and detect_raster_table_lines:
                    r_h, r_v = detect_raster_table_lines(page, y_mid)
                    if len(r_h) >= 2:
                        h_lines = set(r_h)
                        is_raster_table = True
                    if len(r_v) >= 2:
                        v_lines = set(r_v)
                        is_raster_table = True

                sorted_h = sorted(h_lines)
                sorted_v = sorted(v_lines)
                top_lines = [y for y in sorted_h if y <= y_mid]
                bottom_lines = [y for y in sorted_h if y >= y_mid]
                y_top = max(top_lines) if top_lines else y_mid - 25.0
                y_bottom = min(bottom_lines) if bottom_lines else y_mid + 35.0

                # Deteksi batas kolom Nama Personil dan Kolom NO. SC.
                cand_nl = [x for x in sorted_v if 245 <= x <= 275]
                cand_nr = [x for x in sorted_v if 375 <= x <= 405]
                cand_sl = [x for x in sorted_v if 455 <= x <= 475]
                cand_sr = [x for x in sorted_v if 555 <= x <= 575]

                if cand_nl and cand_nr:
                    x_name_left = max(cand_nl)
                    x_name_right = min(cand_nr)
                else:
                    v_between = [x for x in sorted_v if left_dila["bbox"][0] <= x <= sc_label["bbox"][2]]
                    if len(v_between) >= 2:
                        x_name_left, x_name_right = v_between[-2], v_between[-1]
                    else:
                        x_name_left, x_name_right = 267.77, 389.80

                if cand_sl and cand_sr:
                    x_sc_left = max(cand_sl)
                    x_sc_right = min(cand_sr)
                else:
                    v_right = [x for x in sorted_v if x >= sc_label["bbox"][0] - 5.0]
                    if len(v_right) >= 2:
                        x_sc_left, x_sc_right = v_right[-2], v_right[-1]
                    else:
                        x_sc_left, x_sc_right = 467.82, 563.50

                # Safe margin 1.5pt dari seluruh garis sel tabel untuk mencegah bleed stroke shape putih
                y_t_safe = y_top + 1.5
                y_b_safe = y_bottom - 1.5
                sc_r_bound = (max(x_sc_right, 564.0) if is_raster_table else x_sc_right) - 1.5
                rect_sc = fitz.Rect(x_sc_left + 1.5, y_t_safe, sc_r_bound, y_b_safe)
                rect_names = fitz.Rect(x_name_left + 1.5, y_t_safe, x_name_right - 1.5, y_b_safe)

                page.add_redact_annot(rect_names, fill=(1, 1, 1))
                page.add_redact_annot(rect_sc, fill=(1, 1, 1))
                page.apply_redactions()

                if is_raster_table:
                    page.draw_line((x_sc_right + 2.5, y_top), (x_sc_right + 2.5, y_bottom), color=(0, 0, 0), width=0.6)

                num_rows = len(clean_employees)
                avail_h = (y_bottom - 1.0) - (y_top + 1.0)
                row_h = avail_h / (num_rows + 1)

                for idx, emp in enumerate(clean_employees):
                    nm = emp["nama"]
                    sc = emp["no_sc"]
                    y_row_center = (y_top + 1.0) + (idx + 1) * row_h
                    y_base_name = y_row_center + (font_size_name * 0.36)
                    y_base_sc = y_row_center + (font_size_sc * 0.36)

                    w_nm = _calc_w(nm, font_size_name)
                    x_name_pos = max(x_name_left + 2.0, (x_name_left + x_name_right) / 2 - w_nm / 2)
                    page.insert_text((x_name_pos, y_base_name), nm, **insert_kwargs)

                    w_sc = _calc_w(sc, font_size_sc)
                    x_sc_pos = max(x_sc_left + 2.0, (x_sc_left + x_sc_right) / 2 - w_sc / 2)
                    page.insert_text((x_sc_pos, y_base_sc), sc, **insert_sc_kwargs)

        # Simpan ke berkas sementara kemudian swap secara atomik
        doc.save(temp_path, garbage=3, deflate=True)
        doc.close()

        # In-place overwrite langsung berkas asli
        shutil.move(temp_path, pdf_path)
        res["ok"] = True
    except Exception as e:
        res["error"] = str(e)
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass

    return res
