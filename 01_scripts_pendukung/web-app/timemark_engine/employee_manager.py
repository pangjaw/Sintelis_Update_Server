"""
Employee Manager Module for OCR-FOTO-P3STE.

Handles:
1. Loading personnel configuration (KAUR & PNC) from config/daftar_pegawai.json.
2. Detecting personnel assigned to Tim 1 on a given date.
3. Determining consistent Tim 2 roster (1 KAUR on top + 2 PNC below) per date.
4. Clean PDF redaction and insertion of replacement personnel on Page 1.
"""

import os
import sys
import re
import json
import random
from pathlib import Path
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)
try:
    import pymupdf as fitz
except ImportError:
    import fitz

# Default fallback config path
CONFIG_PATH = Path("config/daftar_pegawai.json")


def load_pegawai_config(config_path: Path | str = None) -> dict:
    """Loads KAUR and PNC master data from active config or config/daftar_pegawai.json."""
    p = None
    if config_path and Path(config_path).exists():
        p = Path(config_path)
    else:
        candidates = [
            Path("temp_active_pegawai.json"),
            Path(os.environ.get("LOCALAPPDATA", "")) / "SintelisUtility" / "daftar_pegawai.json",
            CONFIG_PATH,
            Path(__file__).parent.parent / "config" / "daftar_pegawai.json",
            Path(__file__).parent / "daftar_pegawai.json",
        ]
        for cand in candidates:
            if cand.is_file() and cand.stat().st_size > 10:
                p = cand
                break

    if p and p.exists():
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {
                    "resor": data.get("resor", {
                        "nama": "FURQON SUSILO WARDOYO",
                        "nipp": "64465",
                        "jabatan": "KUPT RESOR STL 1.21 BOGOR"
                    }),
                    "kaur": data.get("kaur", []),
                    "pnc": data.get("pnc", [])
                }
        except Exception as e:
            print(f"[WARN] Failed to read {p}: {e}")

    # Default fallback personnel if file is missing
    return {
        "resor": {
            "nama": "FURQON SUSILO WARDOYO",
            "nipp": "64465",
            "jabatan": "KUPT RESOR STL 1.21 BOGOR"
        },
        "kaur": [
            {"nama": "SUTISNA", "nipp": "45677", "no_sc": "PRP.080175.126093"},
            {"nama": "YATIYO", "nipp": "49957", "no_sc": "PRP.260287.39992"}
        ],
        "pnc": [
            {"nama": "RAIHAN HERPIAN", "nipp": "75276", "no_sc": "PRP.170204.72256"},
            {"nama": "IWAN SETIAWAN", "nipp": "69810", "no_sc": "PRP.03071990.36476"},
            {"nama": "JUJUN JUNAEDI", "nipp": "69699", "no_sc": "PRP.02021990.36540"},
            {"nama": "DIKA ARMANSYAH", "nipp": "72347", "no_sc": "PRP.020899.122293"}
        ]
    }


def extract_page1_tim1_personnel(doc: fitz.Document) -> set[str]:
    """Extracts personnel names and SC numbers from Page 1 of a Tim 1 PDF."""
    if len(doc) == 0:
        return set()

    page = doc[0]
    blocks = page.get_text("dict")["blocks"]

    dila_span = None
    sc_span = None

    for b in blocks:
        if "lines" not in b:
            continue
        for l in b["lines"]:
            for s in l["spans"]:
                txt = s["text"].strip().upper()
                if "DILAKSANAKAN" in txt:
                    dila_span = s
                elif "NO. SC." in txt and dila_span and abs(s["bbox"][1] - dila_span["bbox"][1]) < 30:
                    sc_span = s

    if not dila_span:
        return set()

    y_mid = (dila_span["bbox"][1] + dila_span["bbox"][3]) / 2

    # Extract all text in the horizontal band of "Dilaksanakan oleh:" row
    found_tokens = set()
    for b in blocks:
        if "lines" not in b:
            continue
        for l in b["lines"]:
            for s in l["spans"]:
                txt = s["text"].strip().upper()
                # If within vertical band of the personnel row
                if abs(s["bbox"][1] - y_mid) < 35 and s["bbox"][0] > dila_span["bbox"][2]:
                    if txt and txt not in (":", "NO. SC.", "-", "PRP.", "NO.", "SC."):
                        found_tokens.add(txt)
                        # Also add individual words / SC numbers
                        for w in txt.split():
                            if len(w) > 2:
                                found_tokens.add(w)

    return found_tokens


def get_tim2_roster_for_date(
    date_str: str,
    tim1_personnel_tokens: set[str] = None,
    pegawai_config: dict = None
) -> list[dict]:
    """
    Determines 1 KAUR (top row) and 2 PNC (middle & bottom rows) for Tim 2 on date_str.
    Uses exact same deterministic rotation of remaining personnel (not in Tim 1) as audit_and_correct_personnel.py.
    """
    if pegawai_config is None:
        pegawai_config = load_pegawai_config()
    if tim1_personnel_tokens is None:
        tim1_personnel_tokens = set()

    all_kaur = list(pegawai_config.get("kaur", []))
    all_pnc = list(pegawai_config.get("pnc", []))

    if not all_kaur:
        all_kaur = [{"nama": "S. SLAMET RIYADI", "no_sc": "PRP.070474.126088"}]
    if len(all_pnc) < 2:
        all_pnc = [
            {"nama": "AGUS PRIYONO", "no_sc": "PRP.030886.126116"},
            {"nama": "IWAN SETIAWAN", "no_sc": "PRP.03071990.36476"}
        ]

    m_day = re.match(r'^(\d{2})', str(date_str).strip())
    day_num = int(m_day.group(1)) if m_day else 1

    upper_tokens = {str(t).strip().upper() for t in tim1_personnel_tokens if t}

    def is_in_tim1(person: dict) -> bool:
        nama = person.get("nama", "").strip().upper()
        no_sc = person.get("no_sc", "").strip().upper()
        if nama in upper_tokens or (no_sc and no_sc in upper_tokens):
            return True
        return False

    # 1. Select 1 KAUR from remaining KAUR not in Tim 1
    rem_kaur = [k for k in all_kaur if not is_in_tim1(k)]
    chosen_kaur = rem_kaur[0] if rem_kaur else all_kaur[day_num % len(all_kaur)]

    # 2. Select 2 PNCs from remaining PNC not in Tim 1
    rem_pnc = [p for p in all_pnc if not is_in_tim1(p)]
    if len(rem_pnc) >= 2:
        shift = (day_num - 1) % len(rem_pnc)
        chosen_pncs = [rem_pnc[shift], rem_pnc[(shift + 1) % len(rem_pnc)]]
    elif len(rem_pnc) == 1:
        chosen_pncs = [rem_pnc[0]]
        for p in all_pnc:
            if p not in chosen_pncs:
                chosen_pncs.append(p)
                break
    else:
        chosen_pncs = [all_pnc[(day_num - 1) % len(all_pnc)], all_pnc[day_num % len(all_pnc)]]

    return [
        {"role": "KAUR", **chosen_kaur},
        {"role": "PNC", **chosen_pncs[0]},
        {"role": "PNC", **chosen_pncs[1]}
    ]


def get_tim3_roster_for_date(
    date_str: str,
    pegawai_config: dict = None
) -> list[dict]:
    """
    Determines 1 KAUR and 2 PNC for Tim 3 on date_str using once-per-date deterministic random seed,
    matching audit_and_correct_personnel.py 100%.
    """
    if pegawai_config is None:
        pegawai_config = load_pegawai_config()

    all_kaur = list(pegawai_config.get("kaur", []))
    all_pnc = list(pegawai_config.get("pnc", []))

    if not all_kaur:
        all_kaur = [{"nama": "S. SLAMET RIYADI", "no_sc": "PRP.070474.126088"}]
    if len(all_pnc) < 2:
        all_pnc = [
            {"nama": "AGUS PRIYONO", "no_sc": "PRP.030886.126116"},
            {"nama": "IWAN SETIAWAN", "no_sc": "PRP.03071990.36476"}
        ]

    seed = sum(ord(c) for c in f"{str(date_str).strip()}_tim3")
    rng = random.Random(seed)
    chosen_kaur = rng.choice(all_kaur)
    sample_pnc = rng.sample(all_pnc, min(2, len(all_pnc)))
    chosen_pncs = list(sample_pnc)
    while len(chosen_pncs) < 2:
        for p in all_pnc:
            if p not in chosen_pncs:
                chosen_pncs.append(p)
                break

    return [
        {"role": "KAUR", **chosen_kaur},
        {"role": "PNC", **chosen_pncs[0]},
        {"role": "PNC", **chosen_pncs[1]}
    ]



def detect_raster_table_lines(page: fitz.Page, y_mid: float) -> tuple[list[float], list[float]]:
    """
    Computer Vision line detection via Pixmap for scanned or Print-to-PDF documents
    where page.get_drawings() contains no vector line elements.
    Returns (h_lines, v_lines) in PDF point coordinates.
    """
    try:
        from PIL import Image
        import numpy as np

        pix = page.get_pixmap(dpi=150)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples).convert("L")
        arr = np.array(img)
        scale = 72.0 / 150.0

        y_min_px = max(0, int((y_mid - 75.0) / scale))
        y_max_px = min(arr.shape[0], int((y_mid + 75.0) / scale))
        sub = arr[y_min_px:y_max_px, :]

        # Horizontal lines across table region
        x_s_px, x_e_px = int(30.0 / scale), int(min(520.0, page.rect.width - 20) / scale)
        h_mask = np.mean(sub[:, x_s_px:x_e_px] < 120, axis=1) > 0.60
        h_y_list = [round((y_min_px + y) * scale, 2) for y in np.where(h_mask)[0]]
        h_lines = []
        for y in h_y_list:
            if not h_lines or abs(y - h_lines[-1]) > 3.0:
                h_lines.append(y)

        top_lines = [y for y in h_lines if y <= y_mid]
        bottom_lines = [y for y in h_lines if y >= y_mid]
        y_top = max(top_lines) if top_lines else y_mid - 25.0
        y_bottom = min(bottom_lines) if bottom_lines else y_mid + 35.0

        # Vertical lines checked strictly within the row height to eliminate false text stroke detection
        row_top_px = int((y_top + 1.5) / scale)
        row_bot_px = int((y_bottom - 1.5) / scale)
        row_slice = arr[row_top_px:row_bot_px, :]

        # Real table lines are continuous through the row (> 55% dark); text strokes are < 25%
        v_mask = np.mean(row_slice < 120, axis=0) > 0.55
        v_x_list = [round(x * scale, 2) for x in np.where(v_mask)[0]]
        v_lines = []
        for x in v_x_list:
            if not v_lines or abs(x - v_lines[-1]) > 3.0:
                v_lines.append(x)

        return h_lines, v_lines
    except Exception as e:
        print(f"[DEBUG] detect_raster_table_lines fallback failed: {e}")
        return [], []


def replace_page1_employee_names(
    doc: fitz.Document,
    new_employees: list[dict],
    sc_only: bool = False
) -> bool:
    """
    Redacts old personnel names & SC numbers on Page 1 and inserts new_employees.
    With sc_only=True, preserve names and update only SC cells.
    """
    if len(doc) == 0:
        return False

    page = doc[0]

    # SC-only wajib mengikuti baris nama aktual, bukan urutan KAUR/PNC.
    if sc_only:
        profile_by_name = {emp.get('nama', '').strip().upper(): emp for emp in new_employees}
        norm_profiles = {re.sub(r'[^A-Z]', '', k): v for k, v in profile_by_name.items()}

        blocks = page.get_text('dict').get('blocks', [])
        spans = []
        lines = []
        for block in blocks:
            for line in block.get('lines', []):
                line_spans = [s for s in line.get('spans', []) if s.get('text', '').strip()]
                spans.extend(line_spans)
                if line_spans:
                    line_str = " ".join(s['text'].strip() for s in line_spans).upper()
                    lines.append({
                        'text': line_str,
                        'bbox': line['bbox'],
                        'spans': line_spans
                    })

        name_spans = []
        span_emp_map = {}

        # Pass 1: Line-level matching (matches split spans like 'MUHAMAD' + 'SOFYAN')
        matched_norm_names = set()
        for l in lines:
            clean_l = re.sub(r'[^A-Z]', '', l['text'])
            for norm_k, emp in norm_profiles.items():
                if norm_k and (norm_k == clean_l or (len(norm_k) >= 6 and norm_k in clean_l)):
                    cand = {'bbox': l['bbox'], 'text': emp['nama']}
                    name_spans.append(cand)
                    span_emp_map[id(cand)] = emp
                    matched_norm_names.add(norm_k)
                    break

        # Pass 2: Single span matching fallback
        for s in spans:
            clean = re.sub(r'[^A-Z]', '', s.get('text', '')).upper()
            if clean in norm_profiles and clean not in matched_norm_names:
                name_spans.append(s)
                span_emp_map[id(s)] = norm_profiles[clean]
                matched_norm_names.add(clean)

        if not name_spans:
            print('[WARN] Tidak menemukan nama personil untuk koreksi nomor SC.')
            return False

        drawings = page.get_drawings()
        sample_y = sum((s['bbox'][1] + s['bbox'][3]) / 2 for s in name_spans) / len(name_spans)
        verticals = sorted({
            round(d['rect'].x0, 2) for d in drawings
            if d['rect'].width < 2 and d['rect'].height > 5
            and d['rect'].y0 - 1 <= sample_y <= d['rect'].y1 + 1
        })
        if len(verticals) < 2:
            _, r_v = detect_raster_table_lines(page, sample_y)
            if len(r_v) >= 2:
                verticals = sorted(r_v)

        name_right = max(s['bbox'][2] for s in name_spans)
        right_lines = [x for x in verticals if x > name_right + 2]
        separator_index = next(
            (i for i in range(len(right_lines) - 1) if right_lines[i + 1] - right_lines[i] <= 15),
            None
        )
        if separator_index is None or separator_index + 2 >= len(right_lines):
            x_sc_left = 466.0
            x_sc_right = 563.5
            x_label_left = 400.0
            x_label_right = 440.0
        else:
            x_label_left = right_lines[separator_index - 1] if separator_index > 0 else 400.0
            x_label_right = right_lines[separator_index]
            x_sc_left = right_lines[separator_index + 1] + 2.5
            x_sc_right = right_lines[separator_index + 2] - 2.5

        for name_span in name_spans:
            y0, y1 = name_span['bbox'][1], name_span['bbox'][3]
            # Bersihkan hanya nilai SC pada sel kanan; label NO. SC. tetap dipertahankan.
            safe_sc_left = x_sc_left
            safe_sc_right = x_sc_right
            page.add_redact_annot(
                fitz.Rect(safe_sc_left, y0 - 1, safe_sc_right, y1 + 1),
                fill=(1, 1, 1)
            )
            for span in spans:
                text = span['text'].strip().upper()
                if (text.startswith('PRP.') or text.startswith('NIPP.')) and span['bbox'][1] < y1 + 3 and span['bbox'][3] > y0 - 3:
                    s_rect = fitz.Rect(span['bbox'])
                    s_left = max(safe_sc_left, s_rect.x0 - 1)
                    s_right = min(safe_sc_right, s_rect.x1 + 1)
                    page.add_redact_annot(fitz.Rect(s_left, s_rect.y0 - 1, s_right, s_rect.y1 + 1), fill=(1, 1, 1))
        # Deteksi dan bersihkan jika ada teks 'NO. SC.' ganda/duplikat di sel label (akibat koreksi sebelumnya)
        if x_label_left is not None:
            label_spans = [
                s for s in spans
                if 'NO. SC' in s['text'].strip().upper()
                and x_label_left - 10 <= s['bbox'][0] <= x_label_right + 10
                and min(s['bbox'][1] for s in name_spans) - 30 <= s['bbox'][1] <= max(s['bbox'][3] for s in name_spans) + 30
            ]
            if len(label_spans) > 1:
                h_lines = sorted({
                    round(d['rect'].y0, 2) for d in drawings
                    if d['rect'].width > 20 and d['rect'].height < 2
                    and sample_y - 60 <= d['rect'].y0 <= sample_y + 60
                })
                top_lines = [y for y in h_lines if y <= sample_y]
                bottom_lines = [y for y in h_lines if y >= sample_y]
                y_center = ((max(top_lines) if top_lines else sample_y - 25) + (min(bottom_lines) if bottom_lines else sample_y + 35)) / 2
                label_spans.sort(key=lambda s: abs((s['bbox'][1] + s['bbox'][3]) / 2 - y_center))
                for extra_span in label_spans[1:]:
                    rect_extra = fitz.Rect(extra_span['bbox'][0] - 1, extra_span['bbox'][1] + 0.5, extra_span['bbox'][2] + 1, extra_span['bbox'][3] + 0.5)
                    page.add_redact_annot(rect_extra, fill=(1, 1, 1))

        page.apply_redactions()

        font_size = 6.91
        font_candidates = [
            getattr(sys, "_MEIPASS", "") and Path(sys._MEIPASS) / "timemark_engine" / "DejaVuSans-Bold.ttf",
            getattr(sys, "_MEIPASS", "") and Path(sys._MEIPASS) / "config" / "DejaVuSans-Bold.ttf",
            getattr(sys, "_MEIPASS", "") and Path(sys._MEIPASS) / "DejaVuSans-Bold.ttf",
            Path(__file__).parent / "DejaVuSans-Bold.ttf",
            Path(__file__).parent / "config" / "DejaVuSans-Bold.ttf",
            Path(__file__).parent.parent / "config" / "DejaVuSans-Bold.ttf",
            Path("config/DejaVuSans-Bold.ttf"),
            Path("timemark_engine/DejaVuSans-Bold.ttf"),
        ]
        font_file = next((str(p.resolve()) for p in font_candidates if p and Path(p).is_file()), None)
        custom_font = fitz.Font(fontfile=font_file) if font_file else None
        font_name = 'DejaVuSans-Bold' if custom_font else 'hebo'

        # Sesuai instruksi: Selalu gunakan label 'NO. SC.' bawaan template, tidak perlu menulis teks 'NO. SC.' baru.
        for name_span in name_spans:
            emp = span_emp_map.get(id(name_span)) or profile_by_name.get(name_span['text'].strip().upper())
            if not emp:
                continue
            value = emp.get('no_sc', '').strip().upper()
            text_width = custom_font.text_length(value, fontsize=font_size) if custom_font else fitz.get_text_length(value, fontname=font_name, fontsize=font_size)
            x = x_sc_left + (x_sc_right - x_sc_left - text_width) / 2
            y = (name_span['bbox'][1] + name_span['bbox'][3]) / 2 + font_size * 0.36
            kwargs = {'fontname': font_name, 'fontsize': font_size, 'color': (0, 0, 0)}
            if font_file:
                kwargs['fontfile'] = font_file
            page.insert_text((x, y), value, **kwargs)
        return True

    # Full personnel correction retains existing table replacement behavior.
    blocks = page.get_text("dict")["blocks"]
    dila_span = None
    sc_span = None

    # Pass 1: Check line-level spans for DILAKSANAKAN and NO. SC.
    for b in blocks:
        if "lines" not in b:
            continue
        for l in b["lines"]:
            line_str = " ".join(s["text"].strip() for s in l["spans"] if s["text"].strip()).upper()
            spans = l["spans"]
            if "DILAKSANAKAN" in line_str:
                dila_cand = next((s for s in spans if "DILAKSANAKAN" in s["text"].upper()), spans[0])
                if not dila_span or abs(dila_cand["bbox"][1] - 250) < abs(dila_span["bbox"][1] - 250):
                    dila_span = dila_cand
            if "NO. SC" in line_str or "NO.SC" in line_str or ("NO" in line_str and "SC" in line_str):
                sc_spans = [s for s in spans if any(k in s["text"].upper() for k in ["NO", "SC"])]
                if sc_spans:
                    bbox = (
                        min(s["bbox"][0] for s in sc_spans),
                        min(s["bbox"][1] for s in sc_spans),
                        max(s["bbox"][2] for s in sc_spans),
                        max(s["bbox"][3] for s in sc_spans)
                    )
                    sc_cand = {"bbox": bbox, "text": "NO. SC."}
                    if dila_span and abs(bbox[1] - dila_span["bbox"][1]) < 35:
                        sc_span = sc_cand
                    elif not sc_span:
                        sc_span = sc_cand

    # Pass 2: individual spans fallback
    if not dila_span or not sc_span:
        for b in blocks:
            if "lines" not in b:
                continue
            for l in b["lines"]:
                for s in l["spans"]:
                    txt = s["text"].strip().upper()
                    if "DILAKSANAKAN" in txt and not dila_span:
                        dila_span = s
                    elif ("NO. SC" in txt or "NO.SC" in txt) and not sc_span:
                        sc_span = s

    # Pass 3: OCR fallback for scanned/image-only/Print-to-PDF pages
    if not dila_span or not sc_span:
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
            # Crop the table header band (y: 160 to 300 pt) for sharp OCR text segmentation
            y_top_px = int(160.0 / scale)
            y_bot_px = int(min(300.0, page.rect.height) / scale)
            crop_img = img.crop((0, y_top_px, img.width, y_bot_px))

            data = pytesseract.image_to_data(crop_img, output_type=pytesseract.Output.DICT)
            for i in range(len(data["text"])):
                w = data["text"][i].strip().upper()
                if not w:
                    continue
                x0 = data["left"][i] * scale
                y0 = 160.0 + data["top"][i] * scale
                w_pt = data["width"][i] * scale
                h_pt = data["height"][i] * scale
                if ("DILAKSANAKAN" in w or "PILAKSANAKAN" in w or "DILAKS" in w) and not dila_span:
                    dila_span = {"bbox": (x0, y0, x0 + w_pt, y0 + h_pt), "text": "DILAKSANAKAN"}
                elif ("SC" in w or "NO.SC" in w or "NO. SC" in w) and 350 <= x0 <= 480 and not sc_span:
                    sc_span = {"bbox": (max(350.0, x0 - 25.0), y0, x0 + w_pt, y0 + h_pt), "text": "NO. SC."}
        except Exception:
            pass

    # Pass 4: Standard template geometry fallback for A4 portrait forms
    if not dila_span or not sc_span:
        if not dila_span:
            dila_span = {"bbox": (196.6, 246.2, 250.1, 254.1), "text": "DILAKSANAKAN"}
        if not sc_span:
            sc_span = {"bbox": (407.4, 250.5, 436.5, 258.1), "text": "NO. SC."}

    y_mid = (dila_span["bbox"][1] + dila_span["bbox"][3]) / 2
    drawings = page.get_drawings()
    h_lines = set()
    v_lines = set()
    for d in drawings:
        r = d["rect"]
        if r.width > 20 and r.height < 2 and (y_mid - 60 <= r.y0 <= y_mid + 60):
            h_lines.add(round(r.y0, 2))
        elif r.height > 20 and r.width < 2 and (y_mid - 60 <= (r.y0 + r.y1)/2 <= y_mid + 60):
            v_lines.add(round(r.x0, 2))

    is_raster_table = False
    if len(h_lines) < 2 or len(v_lines) < 2:
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
        v_between = [x for x in sorted_v if dila_span["bbox"][0] <= x <= sc_span["bbox"][2]]
        if len(v_between) >= 2:
            x_name_left, x_name_right = v_between[-2], v_between[-1]
        else:
            x_name_left, x_name_right = 267.77, 389.80

    if cand_sl and cand_sr:
        x_sc_left = max(cand_sl)
        x_sc_right = min(cand_sr)
    else:
        v_right = [x for x in sorted_v if x >= sc_span["bbox"][0] - 5.0]
        if len(v_right) >= 2:
            x_sc_left, x_sc_right = v_right[-2], v_right[-1]
        else:
            x_sc_left, x_sc_right = 467.82, 563.50

    # Safe margin 1.5pt dari seluruh garis sel tabel untuk mencegah bleed stroke shape putih
    y_t_safe = y_top + 1.5
    y_b_safe = y_bottom - 1.5
    sc_r_bound = (max(x_sc_right, 564.0) if is_raster_table else x_sc_right) - 1.5
    rect_sc = fitz.Rect(x_sc_left + 1.5, y_t_safe, sc_r_bound, y_b_safe)

    if not sc_only:
        rect_names = fitz.Rect(x_name_left + 1.5, y_t_safe, x_name_right - 1.5, y_b_safe)
        page.add_redact_annot(rect_names, fill=(1, 1, 1))
    page.add_redact_annot(rect_sc, fill=(1, 1, 1))
    page.apply_redactions()

    if is_raster_table:
        # Restore outer right border line cleanly for raster forms
        page.draw_line((x_sc_right + 2.5, y_top), (x_sc_right + 2.5, y_bottom), color=(0, 0, 0), width=0.6)

    num_rows = len(new_employees)
    font_size_name = 7.8
    font_size_sc = 7.0
    ttf_candidates = [
        getattr(sys, "_MEIPASS", "") and Path(sys._MEIPASS) / "timemark_engine" / "DejaVuSans-Bold.ttf",
        getattr(sys, "_MEIPASS", "") and Path(sys._MEIPASS) / "config" / "DejaVuSans-Bold.ttf",
        getattr(sys, "_MEIPASS", "") and Path(sys._MEIPASS) / "DejaVuSans-Bold.ttf",
        Path(__file__).parent / "DejaVuSans-Bold.ttf",
        Path(__file__).parent / "config" / "DejaVuSans-Bold.ttf",
        Path(__file__).parent.parent / "config" / "DejaVuSans-Bold.ttf",
        Path("config/DejaVuSans-Bold.ttf"),
        Path("timemark_engine/DejaVuSans-Bold.ttf"),
    ]
    font_file = next((str(c.resolve()) for c in ttf_candidates if c and Path(c).is_file()), None)
    custom_font = None
    if font_file:
        try:
            custom_font = fitz.Font(fontfile=font_file)
        except Exception:
            pass
    font_name = "DejaVuSans-Bold" if custom_font else "hebo"
    avail_h = (y_bottom - 1.0) - (y_top + 1.0)
    row_h = avail_h / (num_rows + 1)

    for idx, emp in enumerate(new_employees):
        nama = emp.get("nama", "").strip().upper()
        no_sc = emp.get("no_sc", "").strip().upper()
        y_row_center = (y_top + 1.0) + (idx + 1) * row_h
        y_base_name = y_row_center + (font_size_name * 0.36)
        y_base_sc = y_row_center + (font_size_sc * 0.36)
        if not sc_only:
            w_name = custom_font.text_length(nama, fontsize=font_size_name) if custom_font else fitz.get_text_length(nama, fontname=font_name, fontsize=font_size_name)
            x_name_pos = max(x_name_left + 2.0, (x_name_left + x_name_right) / 2 - w_name / 2)
            kwargs = {'fontname': font_name, 'fontsize': font_size_name, 'color': (0, 0, 0)}
            if custom_font: kwargs['fontfile'] = font_file
            page.insert_text((x_name_pos, y_base_name), nama, **kwargs)
        w_sc = custom_font.text_length(no_sc, fontsize=font_size_sc) if custom_font else fitz.get_text_length(no_sc, fontname=font_name, fontsize=font_size_sc)
        x_sc_pos = max(x_sc_left + 2.0, (x_sc_left + x_sc_right) / 2 - w_sc / 2)
        kwargs = {'fontname': font_name, 'fontsize': font_size_sc, 'color': (0, 0, 0)}
        if custom_font: kwargs['fontfile'] = font_file
        page.insert_text((x_sc_pos, y_base_sc), no_sc, **kwargs)

    return True


def deduplicate_no_sc_in_doc(doc: fitz.Document) -> bool:
    """Mendeteksi dan menghapus teks 'NO. SC.' duplikat/dobel di halaman 1 lembar perawatan."""
    if len(doc) == 0:
        return False
    page = doc[0]
    spans = []
    for b in page.get_text('dict')['blocks']:
        for l in b.get('lines', []):
            spans.extend(s for s in l.get('spans', []) if s.get('text', '').strip())

    label_spans = [
        s for s in spans
        if 'NO. SC' in s['text'].strip().upper()
        and 360 <= s['bbox'][0] <= 465
        and 180 <= s['bbox'][1] <= 320
    ]
    if len(label_spans) <= 1:
        return False

    sample_y = sum((s['bbox'][1] + s['bbox'][3]) / 2 for s in label_spans) / len(label_spans)
    drawings = page.get_drawings()
    h_lines = sorted({
        round(d['rect'].y0, 2) for d in drawings
        if d['rect'].width > 20 and d['rect'].height < 2
        and sample_y - 60 <= d['rect'].y0 <= sample_y + 60
    })
    top_lines = [y for y in h_lines if y <= sample_y]
    bottom_lines = [y for y in h_lines if y >= sample_y]
    y_center = ((max(top_lines) if top_lines else sample_y - 25) + (min(bottom_lines) if bottom_lines else sample_y + 35)) / 2

    # Urutkan berdasarkan jarak ke posisi vertikal tengah sel, pertahankan yang paling mendekati tengah
    label_spans.sort(key=lambda s: abs((s['bbox'][1] + s['bbox'][3]) / 2 - y_center))
    for extra_span in label_spans[1:]:
        rect_extra = fitz.Rect(extra_span['bbox'][0] - 1, extra_span['bbox'][1] + 0.5, extra_span['bbox'][2] + 1, extra_span['bbox'][3] + 0.5)
        page.add_redact_annot(rect_extra, fill=(1, 1, 1))
    page.apply_redactions()
    return True

