"""merge_pdf_foto.py — Gabung foto hasil edit (format 2026) ke PDF 2025.

Flat structure: photos_dir/Tim_N/{btp}/{category}/{pdf_stem}/{0,50,100}.jpg
Output: output_dir/Tim_N/{btp}/{category}/{pdf_name}

No funcloc1 logic. Category detected from filename.
"""
import sys
import json
import os
import re
import shutil
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, str(Path(__file__).resolve().parent))
from collections import defaultdict, Counter
from dataclasses import dataclass
import pdfplumber
import fitz  # PyMuPDF
from PIL import Image
import io
import openpyxl
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from datetime import datetime
import argparse

from export_pdf_foto import (
    extract_station_from_description, load_sap_mapping, SAP_MAPPING_PATH,
    detect_category_from_filename, extract_station_from_filename, STATION_TO_BTP,
    extract_identifier, extract_funcloc_from_text, extract_all_funclocs,
    sanitize_segment, determine_btp,
)
from employee_manager import (
    load_pegawai_config, extract_page1_tim1_personnel,
    get_tim2_roster_for_date, replace_page1_employee_names
)

import pytesseract
TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if Path(TESSERACT_PATH).exists():
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

DEFAULT_INPUT_DIR = "./02_pdf_target"
DEFAULT_PHOTOS_DIR = "./04_photos_edited"
DEFAULT_OUTPUT_DIR = "./05_pdf_merged"
CHECKLIST_CONFIG_PATH = "./checklist_types.json"


@dataclass
class AssetRow:
    page_number: int
    code: str
    title: str
    asset_type: str
    detail: str
    top: float
    station: str = "UNKNOWN"


# ── Helpers ─────────────────────────────────────────────────────

def log(msg):
    print(msg, flush=True)


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def sanitize_segment(text: str) -> str:
    text = normalize_spaces(text)
    text = "".join("_" if ord(char) < 32 else char for char in text)
    text = re.sub(r'[<>:\\\"/\\|?*]', "_", text)
    text = re.sub(r"\s+", " ", text).strip(" .")
    return text or "UNKNOWN"


def load_checklist_config(path: str = CHECKLIST_CONFIG_PATH) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        log(f"[WARNING] Checklist config not found at {path}, using defaults")
        return {"search_keyword": "PERAWATAN", "types": {}}


# ── Asset parsing ───────────────────────────────────────────────

def detect_asset_type(code: str, title: str) -> str:
    upper = f"{code} {title}".upper()
    if code.startswith("AXL") or "AXLE COUNTER" in upper:
        return "AXC"
    if code.startswith("WSL") or "WESEL" in upper:
        return "WESEL"
    if code.startswith("SIN") or "SINYAL" in upper:
        return "SINYAL"
    if code.startswith("CDA") or "CATU DAYA" in upper:
        return "CATU_DAYA"
    if code.startswith("JPL") or "PINTU PERLINTASAN" in upper:
        return "PINTU_PERLINTASAN"
    if code.startswith("TLK") or code.startswith("TWR") or "TELEKOMUNIKASI" in upper or "RADIO" in upper or "SERAT OPTIK" in upper or "OTB" in upper:
        return "TELEKOMUNIKASI"
    if code.startswith("CTC") or "CTC" in upper or "CTS" in upper or "DALWAS" in upper:
        return "CTS"
    if code.startswith("INB") or code.startswith("TRA"):
        return "UNKNOWN"
    if "BANGUNAN" in upper or "DATA LOGGER" in upper:
        return "PDSE"
    if "MULTIPLEX" in upper:
        return "PTLS"
    return "UNKNOWN"


def extract_detail(title: str, asset_type: str) -> str:
    original = normalize_spaces(title)

    def after(marker: str) -> str | None:
        match = re.search(re.escape(marker), original, flags=re.IGNORECASE)
        if not match:
            return None
        return normalize_spaces(original[match.end():]).lstrip(": -")

    detail = None
    if asset_type == "AXC":
        detail = after("COUNTER")
    elif asset_type == "WESEL":
        detail = after("ELEKTRIK")
    elif asset_type == "SINYAL":
        detail = after("ELEKTRIK") or after("SINYAL MUKA") or after("SINYAL")
    elif asset_type == "CATU_DAYA":
        detail = after("CATU DAYA") or after("GENSET") or after("UPS") or after("BATTERE") or after("BATT")
    elif asset_type == "PINTU_PERLINTASAN":
        detail = after("PINTU PERLINTASAN") or after("JPL") or after("JPLE") or after("GENTANIK")
    elif asset_type == "TELEKOMUNIKASI":
        detail = after("TELEKOMUNIKASI") or after("RADIO") or after("WAYSTATION") or after("SERAT OPTIK")
    elif asset_type == "CTS":
        detail = after("CTC") or after("PERALATAN") or original
    elif asset_type == "PERSINYALAN_ELEKTRIK":
        detail = after("PERSINYALAN ELEKTRIK") or after("DALAM PERSINYALAN") or after("OTB") or after("BANGUNAN")
    if not detail:
        detail = original
    sanitized = sanitize_segment(detail)
    if "ZP 41B" in sanitized.upper() or "ZP41B" in sanitized.upper():
        sanitized = re.sub(r'ZP\s*41B', 'ZP 41', sanitized, flags=re.IGNORECASE)
    return sanitized


def is_valid_asset_title(title: str) -> bool:
    words = title.split()
    code_pattern = re.compile(r"^[A-Z]{2,4}\d{4,}$")
    if all(code_pattern.match(w) for w in words):
        return False
    upper = title.upper()
    valid_keywords = [
        "AXLE", "COUNTER", "WESEL", "SINYAL", "CATU DAYA", "PINTU PERLINTASAN",
        "TELEKOMUNIKASI", "PERSINYALAN ELEKTRIK", "JPL", "GENTANIK", "RADIO",
        "SERAT OPTIK", "OTB", "BANGUNAN", "GENSET", "UPS", "BATTERE", "PANEL",
        "RECTIFIER", "MESIN", "MOTOR", "TOWER", "ANTENA", "INTERLOCKING", "INPUT",
    ]
    return any(kw in upper for kw in valid_keywords)


def extract_asset_rows(page: pdfplumber.page.Page, sap_mapping: dict = None) -> list[AssetRow]:
    lines = defaultdict(list)
    for word in page.extract_words(use_text_flow=True):
        lines[round(float(word["top"]), 1)].append(word)

    rows = []
    code_pattern = re.compile(r"^[A-Z]{2,4}\d{4,}$")

    for top in sorted(lines):
        words = sorted(lines[top], key=lambda w: float(w["x0"]))
        code_index = None
        code = None
        for idx, word in enumerate(words):
            if code_pattern.match(word["text"]):
                code_index = idx
                code = word["text"]
                break
        if code_index is None or not code:
            continue

        title = normalize_spaces(" ".join(word["text"] for word in words[code_index + 1:])).lstrip(": -")
        if not title or not is_valid_asset_title(title):
            continue

        asset_type = detect_asset_type(code, title)
        detail = extract_detail(title, asset_type)
        station = extract_station_from_description(title, sap_mapping or {}, code)
        rows.append(AssetRow(
            page_number=page.page_number, code=code, title=title,
            asset_type=asset_type, detail=detail, top=top, station=station,
        ))
    return rows


# ── PDF helpers ─────────────────────────────────────────────────

def extract_location_from_filename(filename: str) -> str:
    name = filename.rsplit('.', 1)[0]
    parts = name.split('_')
    if len(parts) >= 3:
        loc = parts[2].strip()
        loc = re.sub(r'\s*\(\d+\)\s*$', '', loc)
        return loc.upper()
    return "BOGOR"


def extract_date_from_page1(page_or_text) -> str:
    text = page_or_text if isinstance(page_or_text, str) else (page_or_text.extract_text() or "")
    m = re.search(r"Tanggal\s*:\s*(\d{4}-\d{2}-\d{2})", text, re.IGNORECASE)
    months_id = {
        1: "Januari", 2: "Februari", 3: "Maret", 4: "April",
        5: "Mei", 6: "Juni", 7: "Juli", 8: "Agustus",
        9: "September", 10: "Oktober", 11: "November", 12: "Desember",
    }
    if m:
        y, mo, d = map(int, m.group(1).split('-'))
        return f"{d:02d} {months_id[mo]} {y}"
    return "06 Januari 2025"


def extract_checklist_title(page_or_text, filename: str, config: dict | None = None) -> str:
    if config is None:
        config = load_checklist_config()
    search_keyword = config.get("search_keyword", "PERAWATAN")
    known_types = config.get("types", {})

    text = page_or_text if isinstance(page_or_text, str) else (page_or_text.extract_text() or "")
    for line in text.split('\n'):
        line_clean = normalize_spaces(line)
        if search_keyword in line_clean.upper():
            if line_clean.upper().startswith("STE"):
                line_clean = line_clean[3:].strip()
            extracted = line_clean.upper()
            for known_type in known_types:
                if known_type in extracted or extracted in known_type:
                    return known_type
            return extracted
    # Fallback from filename
    name = filename.rsplit('.', 1)[0]
    parts = name.split('_')
    if len(parts) >= 2:
        ft = parts[1].strip().upper()
        for known_type in known_types:
            if known_type in ft or ft in known_type:
                return known_type
        return ft

    fn_upper = filename.upper()
    for known_type, short_name in known_types.items():
        if short_name.upper() in fn_upper or known_type.upper() in fn_upper:
            return known_type

    cat = detect_category_from_filename(filename)
    for known_type in known_types:
        if cat in known_type:
            return known_type

    return "PERAWATAN AXLE COUNTER SIEMENS 1 BULANAN"


def get_text_width(text: str, fontname: str, fontsize: float) -> float:
    return fitz.get_text_length(text, fontname=fontname, fontsize=fontsize)


def draw_centered_text(page, text: str, y_baseline: float, fontname: str, fontsize: float):
    w = get_text_width(text, fontname, fontsize)
    x = (page.rect.width - w) / 2
    page.insert_text((x, y_baseline), text, fontname=fontname, fontsize=fontsize, color=(0, 0, 0))


def draw_centered_label(page, text: str, img_x0: float, img_x1: float, y_baseline: float, fontname: str, fontsize: float):
    w = get_text_width(text, fontname, fontsize)
    center_img = (img_x0 + img_x1) / 2
    x = center_img - w / 2
    page.insert_text((x, y_baseline), text, fontname=fontname, fontsize=fontsize, color=(0, 0, 0))


def update_page1_date_text(doc, filename: str):
    """Updates Page 1 date value to match target PDF filename date format at exact original origin."""
    m = re.search(r'(\d{2})-(\d{2})-(\d{4})', filename)
    if not m:
        return
    
    raw_date = m.group(0)
    parts = raw_date.split('-')
    target_date_ymd = f"{parts[2]}-{parts[1]}-{parts[0]}"
    
    page1 = doc[0]
    blocks = page1.get_text("dict")["blocks"]
    date_span = None
    
    for b in blocks:
        if "lines" not in b:
            continue
        for l in b["lines"]:
            for span in l["spans"]:
                txt = span["text"].strip()
                if ("2025" in txt or "2026" in txt) and ("-" in txt or "/" in txt or " " in txt):
                    date_span = span
                    break
            if date_span:
                break
        if date_span:
            break
            
    if date_span:
        bbox = date_span["bbox"]
        origin = date_span["origin"]
        original_txt = date_span["text"].strip()
        new_date_text = target_date_ymd if re.match(r'^\d{4}-\d{2}-\d{2}$', original_txt) else raw_date
        
        # Redact strictly around old date span
        redact_rect = fitz.Rect(bbox[0] - 1.0, bbox[1] - 0.5, bbox[2] + 1.0, bbox[3] + 0.5)
        page1.add_redact_annot(redact_rect, fill=(1, 1, 1))
        page1.apply_redactions()
        
        # Insert at EXACT original origin (x, y) with Helvetica-Bold 7.8pt
        font_name = "hebo"
        font_size = 7.8
        page1.insert_text(origin, new_date_text, fontname=font_name, fontsize=font_size, color=(0, 0, 0))


def draw_header(page, location: str, date_str: str, checklist_title: str):
    draw_centered_text(page, "FOTO DOKUMENTASI", 38.9, "hebo", 7.2)
    draw_centered_text(page, f"{checklist_title} {location}", 53.3, "hebo", 7.2)
    draw_centered_text(page, date_str, 67.7, "hebo", 7.2)


def determine_btp_from_identifier(identifier: str, fallback_text: str = None) -> str:
    """Determine BTP from any identifier format (handles all categories).
    Delegates to canonical determine_btp in export_pdf_foto.py."""
    return determine_btp(identifier, fallback_text)



# ── QR / Barcode Detection for Photo Page Boundary ──────────────

def _has_qr_code(page) -> bool:
    """Check if page has QR code / barcode (digital signature marker).

    Fast skip: only inspect pages that contain embedded images.
    Renders at 100 DPI for fast and lightweight QR code detection.
    """
    try:
        # Fast skip: if page contains no embedded images, it has no signature QR code
        images = page.get_images()
        if not images:
            return False

        pix = page.get_pixmap(dpi=100)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        from pyzbar.pyzbar import decode
        return len(decode(img)) > 0
    except Exception:
        return False


def _delete_photo_pages(doc) -> None:
    """Delete old photo pages from PDF using multi-layer detection.

    Layer 1 (most accurate): QR code boundary — last page with QR = end of checklist.
        All pages after that are photo pages.
    Layer 2: FOTO/DOKUMENTASI/PENUNJANG header in page text.
    Layer 3: Heuristic — >=2 images OR (short text + has image).
        Checklist pages always have long text and no significant images.
    Layer 4: Scanned PDF fallback — if document has < 80 total text chars, use OCR to detect photo pages.
    """
    if len(doc) <= 1:
        return

    # Layer 1: QR code boundary
    last_qr_page = -1
    for i in range(len(doc) - 1):
        text = doc[i].get_text().upper()
        if "FOTO" not in text and _has_qr_code(doc[i]):
            last_qr_page = i

    if last_qr_page >= 0:
        # Delete all pages after the last QR-bearing checklist page
        while len(doc) > last_qr_page + 1:
            doc.delete_page(-1)
        return

    # Check if scanned document (vector text < 80 chars total across all pages)
    total_doc_text = sum(len(p.get_text().strip()) for p in doc)
    is_scanned_doc = (total_doc_text < 80)

    # Layer 2-3 & Layer 4: Heuristic & OCR fallback
    while len(doc) > 1:
        page = doc[-1]
        text = page.get_text().upper().strip()
        images = page.get_image_info()

        if "FOTO" in text or "DOKUMENTASI" in text or "PENUNJANG" in text:
            doc.delete_page(-1)
            continue

        if is_scanned_doc:
            # For scanned pages, inspect top 25% with OCR
            try:
                pix = page.get_pixmap(dpi=100)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                w, h = img.size
                top_crop = img.crop((0, 0, w, int(h * 0.25)))
                ocr_txt = pytesseract.image_to_string(top_crop).upper()
                if "FOTO" in ocr_txt or "DOKUMENTASI" in ocr_txt or "PENUNJANG" in ocr_txt:
                    doc.delete_page(-1)
                    continue
                else:
                    break
            except Exception:
                if len(doc) >= 3:
                    doc.delete_page(-1)
                break
        else:
            is_photo = (
                (len(text) < 80 and len(images) > 0) or
                len(images) >= 2
            )
            if is_photo:
                doc.delete_page(-1)
            else:
                break

    # Fallback: if last page has >=3 images and not scanned, delete it
    if not is_scanned_doc and len(doc) > 0 and len(doc[-1].get_image_info()) >= 3:
        doc.delete_page(-1)


# ── Core Merge ──────────────────────────────────────────────────

def _iter_tim_dirs(photos_dir: Path):
    """Yield all Tim_N directories; Tim comes from the matched photo path."""
    if photos_dir.exists():
        for d in sorted(photos_dir.iterdir()):
            if d.is_dir() and d.name.startswith("Tim_"):
                yield d


def format_date_from_filename(filename: str) -> str | None:
    """Extracts date DD-MM-YYYY from filename and formats as 'DD Bulan YYYY'."""
    m = re.search(r'(\d{2})-(\d{2})-(\d{4})', filename)
    if not m:
        return None
    d_num, m_num, y_num = int(m.group(1)), int(m.group(2)), int(m.group(3))
    months_id = {
        1: "Januari", 2: "Februari", 3: "Maret", 4: "April", 5: "Mei", 6: "Juni",
        7: "Juli", 8: "Agustus", 9: "September", 10: "Oktober", 11: "November", 12: "Desember"
    }
    return f"{d_num:02d} {months_id.get(m_num, '')} {y_num}"


def get_identifier_candidates(identifier: str) -> list[str]:
    """Expand identifier to account for compound stations, aliases, spacing variants, and known exceptions."""
    cands = [identifier]

    # Spacing variants between letters and numbers (e.g. "UB 206 BOO-CLT" <-> "UB206 BOO-CLT")
    m_space = re.search(r'([A-Za-z]+)\s+(\d+)', identifier)
    if m_space:
        collapsed = re.sub(r'([A-Za-z]+)\s+(\d+)', r'\1\2', identifier)
        if collapsed not in cands:
            cands.append(collapsed)
    m_nospace = re.search(r'([A-Za-z]+)(\d+)', identifier)
    if m_nospace:
        expanded = re.sub(r'([A-Za-z]+)(\d+)', r'\1 \2', identifier)
        if expanded not in cands:
            cands.append(expanded)
    all_nospace = identifier.replace(" ", "")
    if all_nospace not in cands:
        cands.append(all_nospace)

    if "RADIO_" in identifier:
        cands.append(identifier.replace("RADIO_", ""))
    else:
        cands.append(f"RADIO_{identifier}")

    if "RUANG RADIO BOO" in identifier:
        if "RUANG RADIO BOO" not in cands:
            cands.append("RUANG RADIO BOO")
        if "ER RADIO RUANG RADIO BOO" not in cands:
            cands.append("ER RADIO RUANG RADIO BOO")

    if identifier == "ZP 41B BOO":
        cands.append("ZP 41 BOO")
    elif identifier == "ZP 41 BOO":
        cands.append("ZP 41B BOO")

    if "JPL 26N" in identifier:
        for s in ["JPL 26N CLT", "JPL 26N BJD", "JPL 26N CLT-BJD", "JPL 26N BJD-CLT"]:
            if s not in cands:
                cands.append(s)

    m0 = re.match(r'^(JPL\s+)0?(\d+[A-Z]?)\s+(.*)$', identifier, re.I)
    if m0:
        try:
            num = int(m0.group(2))
            cands.append(f"{m0.group(1).upper()}{num} {m0.group(3).upper()}")
            cands.append(f"{m0.group(1).upper()}{num:02d} {m0.group(3).upper()}")
        except ValueError:
            pass

    m_comp = re.match(r'^(JPL\s+(?:BNR|\d+[A-Z]?))\s+([A-Z]{2,3}(?:-[A-Z]{2,3})+)$', identifier, re.I)
    if m_comp:
        pfx = m_comp.group(1).upper()
        sts = m_comp.group(2).upper().split('-')
        for st in sts:
            cands.append(f"{pfx} {st}")
        rev = '-'.join(reversed(sts))
        cands.append(f"{pfx} {rev}")

    return list(dict.fromkeys(cands))


def _find_candidate_folders(base_dir: Path, cand: str, expected_suffix: str = "") -> list[Path]:
    """Find matching subfolders for cand, supporting exact match, suffix, and space-insensitive matching."""
    if not base_dir.is_dir():
        return []
    folders = []
    if expected_suffix:
        suf_p = base_dir / f"{cand}{expected_suffix}"
        if suf_p.is_dir():
            folders.append(suf_p)
    exact_p = base_dir / cand
    if exact_p.is_dir() and exact_p not in folders:
        folders.append(exact_p)

    cand_clean = cand.replace(" ", "").upper()
    suf_clean = f"{cand_clean}{expected_suffix.replace(' ', '').upper()}" if expected_suffix else ""
    try:
        for sub in base_dir.iterdir():
            if sub.is_dir() and sub not in folders:
                sub_clean = sub.name.replace(" ", "").upper()
                if (suf_clean and sub_clean == suf_clean) or (sub_clean == cand_clean):
                    folders.append(sub)
    except Exception:
        pass
    return folders


def process_pdf(pdf_path: Path, photos_dir: Path, output_dir: Path,
                 input_root: Path | None = None,
                 sap_mapping: dict | None = None,
                 schedule_map: dict | None = None,
                 tim2_roster_cache: dict | None = None,
                 tim1_personnel_by_date: dict | None = None,
                 pegawai_config: dict | None = None,
                 log_fn: callable | None = None) -> str:
    """Merge edited photos into PDF.
    
    Flat structure. Photo lookup via Funcloc identifier from page 1.
    Photo path: photos_dir/Tim_N/{btp}/{category}/{identifier}/{0,50,100}.jpg
    Output: output_dir/Tim_N/{btp}/{category}/{pdf_name}
    """
    def _log(msg: str):
        if log_fn is not None:
            log_fn(msg)
        else:
            print(msg, flush=True)

    if sap_mapping is None:
        sap_mapping = {}
    if schedule_map is None:
        schedule_map = {}
    
    # ── Detect category from filename ──
    category = detect_category_from_filename(pdf_path.name)

    # ── Load checklist config ──
    config = load_checklist_config()
    identifier_to_line = {}
    
    # ── Read page 1: extract ALL funclocs → identifiers using fitz (fast) ──
    try:
        with fitz.open(str(pdf_path)) as peek_doc:
            if len(peek_doc) == 0:
                return "failed: PDF has 0 pages"
            page1_text = peek_doc[0].get_text() or ""
    except Exception as exc:
        return f"failed: cannot open PDF ({exc})"

    date_str = extract_date_from_page1(page1_text)
    fn_date_str = format_date_from_filename(pdf_path.name)
    if fn_date_str:
        date_str = fn_date_str
    checklist_title = extract_checklist_title(page1_text, pdf_path.name, config)

    # Scan ALL funclocs on page 1
    all_funclocs = extract_all_funclocs(page1_text)
    _log(f"  ├── Funclocs : {len(all_funclocs)} aset pada dokumen")
    # Build list of (identifier, btp) pairs
    # Also auto-detect category from funcloc prefix if filename detection failed
    asset_entries = []
    seen = set()
    for funcloc_line in all_funclocs:
        identifier = extract_identifier(funcloc_line, category)
        if identifier and identifier not in seen:
            seen.add(identifier)
            identifier_to_line[identifier] = funcloc_line.strip()
            btp = determine_btp_from_identifier(identifier, pdf_path.name)
            if btp == "UNKNOWN":
                btp = "BTP JAK"
            # Auto-detect category from funcloc prefix for photo lookup
            photo_category = category
            if category == "UNKNOWN":
                txt = funcloc_line.strip().upper()
                if txt.startswith("WSL"): photo_category = "WESEL"
                elif txt.startswith("SIN"): photo_category = "SINYAL"
                elif txt.startswith("AXL"): photo_category = "AXC"
            asset_entries.append((identifier, btp, photo_category))
            _log(f"  │   ├── [{photo_category}] {identifier} (Wilayah: {btp})")
    
    if not asset_entries:
        # Fallback 1: check schedule_map for this PDF
        if schedule_map and pdf_path.name in schedule_map:
            s_entry = schedule_map[pdf_path.name]
            s_id = s_entry.get("identifier")
            s_cat = s_entry.get("category") or category
            s_btp = s_entry.get("btp") or determine_btp_from_identifier(s_id, pdf_path.name)
            if s_id:
                asset_entries.append((s_id, s_btp, s_cat))
                identifier_to_line[s_id] = s_id
                _log(f"  [MERGE] Fallback identifier from schedule.json: '{s_id}' [{s_cat}] (Wilayah: {s_btp})")

        # Fallback 2: parse target filename
        if not asset_entries:
            try:
                from extract_pdf_dates import parse_target_filename
                target_info = parse_target_filename(pdf_path.name)
                if target_info:
                    t_cat, t_id, _ = target_info
                    t_btp = determine_btp_from_identifier(t_id, pdf_path.name)
                    asset_entries.append((t_id, t_btp, t_cat or category))
                    identifier_to_line[t_id] = t_id
                    _log(f"  [MERGE] Fallback identifier from parsed filename: '{t_id}' [{t_cat}] (Wilayah: {t_btp})")
            except Exception:
                pass

        # Fallback 3: use pdf stem
        if not asset_entries:
            identifier = sanitize_segment(pdf_path.stem)
            btp = determine_btp_from_identifier(identifier, pdf_path.name)
            if btp == "UNKNOWN":
                btp = "BTP JAK"
            asset_entries.append((identifier, btp, category))
            identifier_to_line[identifier] = pdf_path.stem
            _log(f"  [MERGE] Fallback identifier from stem: '{identifier}' (Wilayah: {btp})")
    
    # ── Team comes from schedule.json or photo paths ──
    location = extract_location_from_filename(pdf_path.name)
    assigned_tim = None
    if schedule_map and pdf_path.name in schedule_map:
        assigned_tim = f"Tim_{schedule_map[pdf_path.name].get('tim', 1)}"
    
    # ── Find photos for all identifiers ──
    photo_paths = {}  # identifier -> (0.jpg, 50.jpg, 100.jpg)
    photo_tims = {}   # identifier -> source Tim_N folder
    missing = []

    # Prioritize searching under assigned_tim directory first
    tim_order = []
    if assigned_tim and (photos_dir / assigned_tim).is_dir():
        tim_order.append(photos_dir / assigned_tim)
    for td in _iter_tim_dirs(photos_dir):
        if td not in tim_order:
            tim_order.append(td)

    # Expected date suffix for WESEL if any
    expected_suffix = ""
    m_wsl = re.search(r'(\d{2})-(\d{2})-\d{4}', pdf_path.name)
    if m_wsl:
        expected_suffix = f"_{m_wsl.group(1)}-{m_wsl.group(2)}"

    MULTI_ROW_CATEGORIES = {"SINYAL", "WESEL", "AXC"}
    is_multi_row = (category in MULTI_ROW_CATEGORIES) or any(cat in MULTI_ROW_CATEGORIES for _, _, cat in asset_entries)

    for identifier, btp, photo_category in asset_entries:
        if not is_multi_row and photo_paths:
            # Opsi A: Untuk kategori non-multi-row (PTLS, CATUDAYA, PDSE, dll.),
            # jika sudah menemukan foto untuk 1 aset (1 baris), batasi agar hanya merender 1 baris foto per PDF.
            break

        found = False
        candidates = get_identifier_candidates(identifier)

        def _check_folder_photos(folder: Path):
            f0, f50, f100 = folder / "0.jpg", folder / "50.jpg", folder / "100.jpg"
            if f0.is_file() and f50.is_file() and f100.is_file():
                is_manual = False
                meta_file = folder / "meta.json"
                if meta_file.is_file():
                    try:
                        m_data = json.loads(meta_file.read_text(encoding="utf-8"))
                        for item in m_data.values():
                            if isinstance(item, dict) and item.get("manualEdit"):
                                is_manual = True
                                break
                    except Exception:
                        pass
                latest_mtime = max(f0.stat().st_mtime, f50.stat().st_mtime, f100.stat().st_mtime)
                return (f0, f50, f100), is_manual, latest_mtime
            return None

        # 1. Search in prioritized tim_order with BTP and photo_category
        # Prioritize candidates in order: exact match (candidates[0]) first!
        for cand in candidates:
            cand_matches = []
            for tim_dir in tim_order:
                base_dir = tim_dir / btp / photo_category
                if not base_dir.is_dir():
                    continue
                target_folders = _find_candidate_folders(base_dir, cand, expected_suffix)
                for tf in target_folders:
                    res = _check_folder_photos(tf)
                    if res:
                        files, is_manual, latest_mtime = res
                        cand_matches.append({
                            "files": files,
                            "tim": tim_dir.name,
                            "is_manual": is_manual,
                            "latest_mtime": latest_mtime,
                            "is_assigned": (assigned_tim and tim_dir.name == assigned_tim)
                        })
            if cand_matches:
                cand_matches.sort(key=lambda x: (
                    1 if x["is_manual"] else 0,
                    x["latest_mtime"],
                    1 if x["is_assigned"] else 0
                ), reverse=True)
                best = cand_matches[0]
                photo_paths[identifier] = best["files"]
                photo_tims[identifier] = best["tim"]
                found = True
                _log(f"  │   ├── 📷 Foto [{identifier}]: {best['files'][0].parent.name} ({best['tim']})")
                break

        # 2. Also try direct (no Tim_N prefix)
        if not found:
            for cand in candidates:
                direct = photos_dir / btp / photo_category
                if direct.is_dir():
                    target_folders = _find_candidate_folders(direct, cand, expected_suffix)
                    for tf in target_folders:
                        res = _check_folder_photos(tf)
                        if res:
                            photo_paths[identifier] = res[0]
                            photo_tims[identifier] = None
                            found = True
                            _log(f"  │   ├── 📷 Foto direct [{identifier}]: {res[0][0].parent.name}")
                            break
                if found:
                    break

        # 3. Cross-BTP search if still not found
        if not found:
            for cand in candidates:
                cross_matches = []
                for tim_dir in tim_order:
                    for btp_dir in sorted(tim_dir.iterdir()):
                        if not btp_dir.is_dir():
                            continue
                        cat_dir = btp_dir / photo_category
                        if not cat_dir.is_dir():
                            continue
                        target_folders = _find_candidate_folders(cat_dir, cand, expected_suffix)
                        for tf in target_folders:
                            res = _check_folder_photos(tf)
                            if res:
                                files, is_manual, latest_mtime = res
                                cross_matches.append({
                                    "files": files,
                                    "tim": tim_dir.name,
                                    "is_manual": is_manual,
                                    "latest_mtime": latest_mtime,
                                    "is_assigned": (assigned_tim and tim_dir.name == assigned_tim)
                                })
                if cross_matches:
                    cross_matches.sort(key=lambda x: (
                        1 if x["is_manual"] else 0,
                        x["latest_mtime"],
                        1 if x["is_assigned"] else 0
                    ), reverse=True)
                    best = cross_matches[0]
                    photo_paths[identifier] = best["files"]
                    photo_tims[identifier] = best["tim"]
                    found = True
                    _log(f"  │   ├── 📷 Foto cross-BTP [{identifier}]: {best['files'][0].parent.name} ({best['tim']})")
                    break

        if not found:
            missing.append(f"{identifier} ({btp}/{photo_category})")
    
    if not photo_paths:
        return f"failed: no matching edited photos found in {photos_dir.name}; output Tim cannot be determined"
    
    output_tim = assigned_tim
    if not output_tim and photo_tims:
        valid_tims = [t for t in photo_tims.values() if t]
        if valid_tims:
            output_tim = Counter(valid_tims).most_common(1)[0][0]
    if not output_tim:
        output_tim = "Tim_1"

    if missing:
        _log(f"  │   ├── ⚠️ [MISSING] Foto belum lengkap: {', '.join(missing)}")
    
    # ── Build merged PDF ──
    doc = fitz.open(str(pdf_path))
    update_page1_date_text(doc, pdf_path.name)

    # ── Update Tim 2 employee names on Page 1 if assigned to Tim 2 ──
    if output_tim == "Tim_2":
        m_date = re.search(r'(\d{2})-(\d{2})-(\d{4})', pdf_path.name)
        d_key = m_date.group(0) if m_date else date_str
        if tim2_roster_cache is not None:
            if d_key not in tim2_roster_cache:
                t1_tokens = tim1_personnel_by_date.get(d_key, set()) if tim1_personnel_by_date else set()
                tim2_roster_cache[d_key] = get_tim2_roster_for_date(d_key, t1_tokens, pegawai_config)
            roster = tim2_roster_cache[d_key]
        else:
            t1_tokens = tim1_personnel_by_date.get(d_key, set()) if tim1_personnel_by_date else set()
            roster = get_tim2_roster_for_date(d_key, t1_tokens, pegawai_config)
        replace_page1_employee_names(doc, roster)

    # Remove all old photo pages (3-layer: QR code → header → heuristic)
    _delete_photo_pages(doc)

    # Create new photo pages
    assets_per_page = 4
    entry_list = list(photo_paths.items())
    page_count_after = 0
    
    for i, (identifier, (f0_path, f50_path, f100_path)) in enumerate(entry_list):
        page_idx = i // assets_per_page
        asset_idx_on_page = i % assets_per_page
        
        if asset_idx_on_page == 0:
            page = doc.new_page(width=595, height=842)
            draw_header(page, location, date_str, checklist_title)
            page_count_after += 1
        
        page = doc[-1]
        
        # Asset title (resolve display title from original checklist line)
        base_id = identifier
        if "_" in identifier:
            parts = identifier.split("_")
            if len(parts) > 1 and re.match(r'^\d{2}-\d{2}$', parts[-1]):
                base_id = "_".join(parts[:-1])
        display_title = identifier_to_line.get(base_id, identifier)
        
        y_title_base = 82.1 + asset_idx_on_page * 183
        page.insert_text((31.5, y_title_base), display_title, fontname="helv", fontsize=7.2, color=(0, 0, 0))
        
        # Photos
        y_img_top = 89.1 + asset_idx_on_page * 183
        y_img_bottom = y_img_top + 148.8
        
        rect_col0 = fitz.Rect(31.5, y_img_top, 180.3, y_img_bottom)
        page.insert_image(rect_col0, filename=str(f0_path))
        
        rect_col1 = fitz.Rect(210.4, y_img_top, 359.2, y_img_bottom)
        page.insert_image(rect_col1, filename=str(f50_path))
        
        rect_col2 = fitz.Rect(389.8, y_img_top, 538.6, y_img_bottom)
        page.insert_image(rect_col2, filename=str(f100_path))
        
        # Labels
        y_label_base = 251.3 + asset_idx_on_page * 183
        draw_centered_label(page, "Foto 0%", 31.5, 180.3, y_label_base, "helv", 7.2)
        draw_centered_label(page, "Foto 50%", 210.4, 359.2, y_label_base, "helv", 7.2)
        draw_centered_label(page, "Foto 100%", 389.8, 538.6, y_label_base, "helv", 7.2)
    
    # ── Save output ──
    first_btp = asset_entries[0][1] if asset_entries else determine_btp(pdf_path.name)
    if first_btp == "UNKNOWN":
        first_btp = "BTP JAK"
    first_category = asset_entries[0][2] if asset_entries else category
    out_pdf_path = output_dir / output_tim / first_btp / first_category / pdf_path.name
    
    ensure_dir(out_pdf_path.parent)
    
    if os.environ.get("OVERWRITE", "1") == "0" and out_pdf_path.exists():
        doc.close()
        return f"skipped: {out_pdf_path.name} sudah ada (overwrite=off)"
    
    try:
        doc.save(str(out_pdf_path))
    except Exception as save_err:
        try:
            temp_out = out_pdf_path.with_name(f"{out_pdf_path.stem}_tmp_{os.getpid()}{out_pdf_path.suffix}")
            doc.save(str(temp_out))
            doc.close()
            temp_out.replace(out_pdf_path)
        except Exception:
            doc.close()
            return f"failed: cannot save {out_pdf_path.name} (file may be open in viewer/browser): {save_err}"
    else:
        doc.close()

    _log(f"  ├── PDF Baru : {out_pdf_path.name} ({len(entry_list)} aset)")

    # ── Copy unedited source photos to PDF output folder ──
    for identifier, (f0_path, f50_path, f100_path) in photo_paths.items():
        for photo_label, photo_path in [("0", f0_path), ("50", f50_path), ("100", f100_path)]:
            flag_path = photo_path.with_suffix(photo_path.suffix + ".unedited")
            if flag_path.exists():
                copy_name = f"{photo_label}_{sanitize_segment(identifier)}.jpg"
                copy_dst = out_pdf_path.parent / copy_name
                shutil.copy2(photo_path, copy_dst)
                _log(f"  [MERGE] Unedited -> {copy_dst}")

    return "ok"

    return "ok"


# ── Auto-export Gagal & Fallback ──
def export_gagal_fallback(logs_dir: Path, failed_files: list = None, skipped_files: list = None) -> None:
    """Auto-export GAGAL_FALLBACK Excel (.xlsx) and companion JSON (.json) after step 5 merge.
    Gathers:
    1. Step 5 Merge Failures (from failed_files or logs/merge_failed.xlsx)
    2. Step 5 Skipped Files (from skipped_files or logs/merge_skipped.xlsx)
    3. Step 4 Edit Failures (from logs/edit_failed.xlsx)
    4. Step 4 Fallback Stages (from logs/edit_stages.xlsx)
    """
    from collections import Counter

    # Detect month
    month = ""
    pdf_dir = Path("02_pdf_target")
    if pdf_dir.is_dir():
        pdf_files = list(pdf_dir.rglob("*.pdf"))
        if pdf_files:
            name = pdf_files[0].stem
            # Try "DD-MM-YYYY" or "YYYY-MM-DD" in filename
            m = re.search(r'(\d{1,2})-(\d{1,2})-(\d{4})', name)
            if not m:
                m = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', name)
            if m:
                try:
                    d = (int(m[3]) if len(m[3])==4 else int(m[1]))
                    mth = (int(m[2]) if len(m[3])==4 else int(m[2]))
                    y = d if d > 2000 else (int(m[3]) if len(m[3])!=4 else int(m[1]))
                    bulan = ["JANUARI","FEBRUARI","MARET","APRIL","MEI","JUNI",
                             "JULI","AGUSTUS","SEPTEMBER","OKTOBER","NOVEMBER","DESEMBER"][mth-1]
                    month = f"{bulan}_{y}"
                except:
                    pass
    if not month:
        month = datetime.now().strftime("UNKNOWN_%Y%m")

    log(f"[EXPORT] Generating {month}_GAGAL_FALLBACK.xlsx & .json ...")

    # Load schedule.json for rich metadata mapping
    sched_map = {}
    sched_path = Path("schedule.json")
    if sched_path.is_file():
        try:
            s_raw = json.loads(sched_path.read_text(encoding="utf-8"))
            for item in s_raw.get("schedules", []):
                if item.get("file"):
                    sched_map[item["file"]] = item
        except Exception:
            pass

    # 1. Gather Gagal Merge (Step 5)
    gagal_merge_list = []
    if failed_files is not None:
        for f in failed_files:
            fn = f.get("file", "")
            s_entry = sched_map.get(fn, {})
            gagal_merge_list.append({
                "file": fn,
                "category": s_entry.get("category") or detect_category_from_filename(fn),
                "identifier": s_entry.get("identifier", ""),
                "btp": s_entry.get("btp", ""),
                "tim": f"Tim_{s_entry.get('tim', 1)}" if s_entry.get("tim") else "",
                "alasan": f.get("reason", ""),
                "timestamp": f.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            })
    else:
        mf_path = logs_dir / "merge_failed.xlsx"
        if mf_path.exists():
            try:
                wb_mf = openpyxl.load_workbook(str(mf_path))
                for r in wb_mf.active.iter_rows(min_row=2, values_only=True):
                    if r and r[0]:
                        fn = str(r[0])
                        s_entry = sched_map.get(fn, {})
                        gagal_merge_list.append({
                            "file": fn,
                            "category": s_entry.get("category") or detect_category_from_filename(fn),
                            "identifier": s_entry.get("identifier", ""),
                            "btp": s_entry.get("btp", ""),
                            "tim": f"Tim_{s_entry.get('tim', 1)}" if s_entry.get("tim") else "",
                            "alasan": str(r[1]) if len(r) > 1 else "",
                            "timestamp": str(r[2]) if len(r) > 2 else ""
                        })
                wb_mf.close()
            except Exception:
                pass

    # 2. Gather Gagal Edit (Step 4)
    gagal_edit_list = []
    fail_path = logs_dir / "edit_failed.xlsx"
    if fail_path.exists():
        try:
            wb_fail = openpyxl.load_workbook(str(fail_path))
            for r in wb_fail.active.iter_rows(min_row=2, values_only=True):
                if r and r[0]:
                    gagal_edit_list.append({
                        "file": str(r[0]),
                        "category": str(r[1]) if len(r) > 1 and r[1] else "",
                        "detail": str(r[2]) if len(r) > 2 and r[2] else "",
                        "photo": str(r[3]) if len(r) > 3 and r[3] else "",
                        "alasan": str(r[4]) if len(r) > 4 and r[4] else "",
                        "timestamp": str(r[5]) if len(r) > 5 and r[5] else ""
                    })
            wb_fail.close()
        except Exception:
            pass

    # 3. Gather Fallback (Step 4)
    fallback_list = []
    st_path = logs_dir / "edit_stages.xlsx"
    if st_path.exists():
        try:
            wb_st = openpyxl.load_workbook(str(st_path))
            for r in wb_st.active.iter_rows(min_row=2, values_only=True):
                if r and len(r) > 1 and r[1] == "stage_fallback":
                    fn = str(r[0])
                    parts = fn.replace("\\\\", "\\").split("\\")
                    fallback_list.append({
                        "file": fn,
                        "category": str(r[2]) if len(r) > 2 and r[2] else "",
                        "detail": str(r[3]) if len(r) > 3 and r[3] else "",
                        "btp": parts[0] if parts else "",
                        "penyebab": "NO red guide detected"
                    })
            wb_st.close()
        except Exception:
            pass

    # 4. Gather Skipped Merge (Step 5)
    skipped_merge_list = []
    if skipped_files is not None:
        for s in skipped_files:
            skipped_merge_list.append({
                "file": s.get("file", ""),
                "alasan": s.get("reason", ""),
                "timestamp": s.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            })
    else:
        sk_path = logs_dir / "merge_skipped.xlsx"
        if sk_path.exists():
            try:
                wb_sk = openpyxl.load_workbook(str(sk_path))
                for r in wb_sk.active.iter_rows(min_row=2, values_only=True):
                    if r and r[0]:
                        skipped_merge_list.append({
                            "file": str(r[0]),
                            "alasan": str(r[1]) if len(r) > 1 else "",
                            "timestamp": str(r[2]) if len(r) > 2 else ""
                        })
                wb_sk.close()
            except Exception:
                pass

    # ── Write Excel ──
    header_font = Font(bold=True, color="FFFFFF", size=11)
    red_fill = PatternFill("solid", fgColor="C0392B")
    orange_fill = PatternFill("solid", fgColor="D35400")
    blue_fill = PatternFill("solid", fgColor="2980B9")
    gray_fill = PatternFill("solid", fgColor="7F8C8D")

    wb = openpyxl.Workbook()

    # Sheet 1: GAGAL MERGE
    ws1 = wb.active
    ws1.title = "GAGAL_MERGE"
    headers_gm = ["No", "File PDF", "Category", "Detail Aset", "Tim", "Alasan", "Timestamp"]
    for ci, h in enumerate(headers_gm, 1):
        c = ws1.cell(row=1, column=ci, value=h)
        c.font = header_font; c.fill = red_fill; c.alignment = Alignment(horizontal="center")
    for idx, item in enumerate(gagal_merge_list, 1):
        ws1.append([idx, item["file"], item["category"], item["identifier"], item["tim"], item["alasan"], item["timestamp"]])
    ws1.column_dimensions["A"].width = 6
    ws1.column_dimensions["B"].width = 52
    ws1.column_dimensions["C"].width = 14
    ws1.column_dimensions["D"].width = 25
    ws1.column_dimensions["E"].width = 10
    ws1.column_dimensions["F"].width = 45
    ws1.column_dimensions["G"].width = 22

    # Sheet 2: GAGAL EDIT (Step 4)
    ws2 = wb.create_sheet("GAGAL_EDIT")
    headers_ge = ["No", "File", "Category", "Detail Aset", "Photo", "Alasan", "Timestamp"]
    for ci, h in enumerate(headers_ge, 1):
        c = ws2.cell(row=1, column=ci, value=h)
        c.font = header_font; c.fill = red_fill; c.alignment = Alignment(horizontal="center")
    for idx, item in enumerate(gagal_edit_list, 1):
        ws2.append([idx, item["file"], item["category"], item["detail"], item["photo"], item["alasan"], item["timestamp"]])
    for ci, col in enumerate(["A","B","C","D","E","F","G"]):
        ws2.column_dimensions[col].width = [6, 48, 12, 28, 8, 35, 22][ci]

    # Sheet 3: FALLBACK (Step 4)
    ws3 = wb.create_sheet("FALLBACK_STAGE")
    headers_fb = ["No", "File", "Category", "Detail Aset", "BTP", "Penyebab"]
    for ci, h in enumerate(headers_fb, 1):
        c = ws3.cell(row=1, column=ci, value=h)
        c.font = header_font; c.fill = orange_fill; c.alignment = Alignment(horizontal="center")
    for idx, item in enumerate(fallback_list, 1):
        ws3.append([idx, item["file"], item["category"], item["detail"], item["btp"], item["penyebab"]])
    for ci, col in enumerate(["A","B","C","D","E","F"]):
        ws3.column_dimensions[col].width = [6, 52, 15, 28, 12, 28][ci]

    # Sheet 4: SKIPPED
    ws4 = wb.create_sheet("SKIPPED_MERGE")
    headers_sk = ["No", "File PDF", "Alasan", "Timestamp"]
    for ci, h in enumerate(headers_sk, 1):
        c = ws4.cell(row=1, column=ci, value=h)
        c.font = header_font; c.fill = gray_fill; c.alignment = Alignment(horizontal="center")
    for idx, item in enumerate(skipped_merge_list, 1):
        ws4.append([idx, item["file"], item["alasan"], item["timestamp"]])
    for ci, col in enumerate(["A","B","C","D"]):
        ws4.column_dimensions[col].width = [6, 52, 45, 22][ci]

    # Sheet 5: SUMMARY
    ws5 = wb.create_sheet("SUMMARY")
    ws5.merge_cells("A1:D1")
    ws5.cell(row=1, column=1, value=f"{month} \u2014 REKAPITULASI GAGAL & FALLBACK").font = Font(bold=True, size=14, color="1A5276")

    n_gm = len(gagal_merge_list)
    n_ge = len(gagal_edit_list)
    n_fb = len(fallback_list)
    n_sk = len(skipped_merge_list)

    ws5.cell(row=3, column=1, value="Kategori Masalah").font = Font(bold=True)
    ws5.cell(row=3, column=2, value="Jumlah Berkas").font = Font(bold=True)
    ws5.cell(row=4, column=1, value="Gagal Merge PDF (Step 5)"); ws5.cell(row=4, column=2, value=n_gm)
    ws5.cell(row=5, column=1, value="Gagal Edit Watermark (Step 4)"); ws5.cell(row=5, column=2, value=n_ge)
    ws5.cell(row=6, column=1, value="Fallback Stage (Step 4)"); ws5.cell(row=6, column=2, value=n_fb)
    ws5.cell(row=7, column=1, value="Dilewati / Skipped (Step 5)"); ws5.cell(row=7, column=2, value=n_sk)
    ws5.cell(row=8, column=1, value="TOTAL KASUS").font = Font(bold=True); ws5.cell(row=8, column=2, value=n_gm + n_ge + n_fb).font = Font(bold=True)

    # Category breakdown for Gagal Merge
    cat_gm = Counter(item["category"] for item in gagal_merge_list if item.get("category"))
    ws5.cell(row=10, column=1, value="Rincian Gagal Merge per Kategori").font = Font(bold=True, size=11)
    ws5.cell(row=11, column=1, value="Kategori"); ws5.cell(row=11, column=2, value="Jumlah"); ws5.cell(row=11, column=3, value="%")
    for i, (cat, cnt) in enumerate(sorted(cat_gm.items()), 12):
        ws5.cell(row=i, column=1, value=cat); ws5.cell(row=i, column=2, value=cnt)
        ws5.cell(row=i, column=3, value=f"{cnt/n_gm*100:.1f}%" if n_gm else "0%")

    ws5.column_dimensions["A"].width = 35
    ws5.column_dimensions["B"].width = 15
    ws5.column_dimensions["C"].width = 10

    # Save Excel
    out_xlsx = logs_dir / f"{month}_GAGAL_FALLBACK.xlsx"
    try:
        wb.save(str(out_xlsx))
    except PermissionError:
        log(f"[WARNING] Tidak dapat menimpa {out_xlsx.name} karena sedang dibuka di program lain (Excel).")

    # Save Companion JSON
    json_data = {
        "month": month,
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "gagal_merge": n_gm,
            "gagal_edit": n_ge,
            "fallback_edit": n_fb,
            "skipped_merge": n_sk,
            "total_issues": n_gm + n_ge + n_fb
        },
        "gagal_merge": gagal_merge_list,
        "gagal_edit": gagal_edit_list,
        "fallback_edit": fallback_list,
        "skipped_merge": skipped_merge_list
    }
    out_json = logs_dir / f"{month}_GAGAL_FALLBACK.json"
    out_json.write_text(json.dumps(json_data, indent=2, ensure_ascii=False), encoding="utf-8")

    log(f"[EXPORT] -> {out_xlsx} & {out_json} (Gagal Merge: {n_gm}, Gagal Edit: {n_ge}, Fallback: {n_fb})")


# ── Main ────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description="Gabungkan foto hasil edit ke PDF (flat structure).")
    p.add_argument("--input", default=DEFAULT_INPUT_DIR)
    p.add_argument("--photos", default=DEFAULT_PHOTOS_DIR)
    p.add_argument("--output", default=DEFAULT_OUTPUT_DIR)
    p.add_argument("--file", default=None, help="Nama atau path berkas PDF spesifik untuk diproses saja")
    return p.parse_args()


def _merge_worker_wrapper(args_tuple):
    pdf_path, photos_dir, output_dir, input_dir, sap_mapping, schedule_map, tim2_roster_cache, tim1_personnel_by_date, pegawai_config = args_tuple
    captured_lines = []
    try:
        status = process_pdf(pdf_path, photos_dir, output_dir, input_dir, sap_mapping, schedule_map,
                             tim2_roster_cache, tim1_personnel_by_date, pegawai_config,
                             log_fn=captured_lines.append)
    except Exception as exc:
        status = f"failed: exception {exc}"
    return pdf_path, status, captured_lines


def main():
    sap_path = SAP_MAPPING_PATH
    if not Path(sap_path).exists() and Path("config/sap_station_mapping.json").exists():
        sap_path = "config/sap_station_mapping.json"
    sap_mapping = load_sap_mapping(sap_path)

    # Load schedule.json for team assignment
    schedule_map = {}
    sched_path = Path("schedule.json")
    if sched_path.exists():
        try:
            with open(sched_path, "r", encoding="utf-8") as f:
                s_data = json.load(f)
                for s in s_data.get("schedules", []):
                    if "file" in s:
                        schedule_map[s["file"]] = s
        except Exception as e:
            log(f"[WARNING] Cannot load schedule.json: {e}")

    args = parse_args()
    input_dir = Path(args.input).resolve()
    photos_dir = Path(args.photos).resolve()
    output_dir = Path(args.output).resolve()

    if not input_dir.is_dir():
        print(f"Folder input tidak ditemukan: {input_dir}")
        return 1
    if not photos_dir.is_dir():
        print(f"Folder foto hasil edit tidak ditemukan: {photos_dir}")
        return 1

    ensure_dir(output_dir)

    pdf_files = sorted([p for p in input_dir.rglob("*")
                        if p.is_file() and p.suffix.lower() == ".pdf"])
    if not pdf_files:
        print(f"Tidak ada berkas PDF di: {input_dir}")
        return 0

    if args.file:
        raw_names = [f.strip().lower() for f in args.file.split(",") if f.strip()]
        pdf_files = [p for p in pdf_files if p.name.lower() in raw_names]
        if not pdf_files:
            log(f"Berkas PDF '{args.file}' tidak ditemukan di: {input_dir}")
            return 1
        log(f"[SPECIFIC-FILES MODE] Memproses {len(pdf_files)} berkas spesifik:")
        for pf in pdf_files:
            log(f"  • {pf.name}")

    log(f"Mulai pemrosesan {len(pdf_files)} berkas PDF...")
    log(f"Tim routing: schedule.json + source photo paths under {photos_dir.name}/Tim_N")
    log(f"Input:  {input_dir}")
    log(f"Photos: {photos_dir}")
    log(f"Output: {output_dir}\n")

    # Load employee master config and pre-scan Tim 1 personnel per date
    pegawai_config = load_pegawai_config()
    tim1_personnel_by_date = defaultdict(set)
    tim2_roster_cache = {}

    for p in pdf_files:
        assigned_tim_num = schedule_map.get(p.name, {}).get("tim", 1)
        if assigned_tim_num == 1:
            m_dt = re.search(r'(\d{2})-(\d{2})-(\d{4})', p.name)
            d_k = m_dt.group(0) if m_dt else "DEFAULT"
            if d_k not in tim1_personnel_by_date:
                try:
                    with fitz.open(str(p)) as doc_scan:
                        t1_toks = extract_page1_tim1_personnel(doc_scan)
                        if t1_toks:
                            tim1_personnel_by_date[d_k].update(t1_toks)
                except Exception:
                    pass

    success = 0
    skipped = 0
    failed = 0
    failed_files = []
    skipped_files = []

    import concurrent.futures

    max_workers = min(len(pdf_files), 4 if args.file else min(4, os.cpu_count() or 2))
    tasks = [
        (p, photos_dir, output_dir, input_dir, sap_mapping, schedule_map,
         tim2_roster_cache, tim1_personnel_by_date, pegawai_config)
        for p in pdf_files
    ]

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_pdf = {executor.submit(_merge_worker_wrapper, t): t[0] for t in tasks}
        for idx, future in enumerate(concurrent.futures.as_completed(future_to_pdf), 1):
            pdf_path, status, captured_lines = future.result()
            log(f"[{idx}/{len(pdf_files)}] 📄 {pdf_path.name}")
            if captured_lines:
                for line in captured_lines:
                    if line.strip():
                        print(line, flush=True)

            if status == "ok":
                success += 1
                log(f"  └── [OK] Berhasil digabung ke folder PDF output\n")
                # Auto-koreksi core jika berkas Serat Optik / OTB
                if "SERAT OPTIK" in pdf_path.name.upper() or "OTB" in pdf_path.name.upper():
                    try:
                        from correct_serat_optik_cores import apply_core_correction, get_core_info
                        merged_candidates = list(output_dir.rglob(pdf_path.name))
                        for m_pdf in merged_candidates:
                            c_info = get_core_info(m_pdf)
                            if c_info and c_info.get("needs_correction"):
                                ok_c, msg_c = apply_core_correction(m_pdf, c_info["target_core"], make_backup=False)
                                log(f"  └── [CORE OPTIK] {msg_c} -> {c_info['target_core']} Core")
                    except Exception as e_c:
                        log(f"  └── [WARNING CORE] Gagal koreksi core: {e_c}")
            elif status.startswith("skipped"):
                skipped += 1
                skipped_files.append({
                    "file": pdf_path.name, "reason": status,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                log(f"  └── [SKIP] {status}\n")
            else:
                failed += 1
                failed_files.append({
                    "file": pdf_path.name, "reason": status,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                log(f"  └── ❌ [FAIL] {status}\n")

    if args.file:
        merged_outputs = {}
        for pf in pdf_files:
            mc = list(output_dir.rglob(pf.name))
            if mc:
                merged_outputs[pf.name] = str(mc[0])
        out_p = list(merged_outputs.values())[0] if merged_outputs else ""
        summary = {
            "step": "merge",
            "success": success,
            "failed": failed,
            "skipped": skipped,
            "single_file": pdf_files[0].name if len(pdf_files) == 1 else None,
            "files": [p.name for p in pdf_files],
            "outputs": merged_outputs,
            "outputPath": out_p,
            "status": "ok" if success > 0 else "failed"
        }
        print(f"__SUMMARY__:{json.dumps(summary)}", flush=True)
        log(f"\n[SPECIFIC-FILES DONE] Selesai memproses {len(pdf_files)} berkas: {success} sukses, {failed} gagal.")
        return 0 if success > 0 else 1

    # Export Excel logs
    logs_dir = Path("logs")
    ensure_dir(logs_dir)

    if failed_files:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Failed Files"
        for col, h in enumerate(["File PDF", "Alasan", "Timestamp"], 1):
            c = ws.cell(row=1, column=col, value=h)
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = PatternFill(start_color="FF4444", end_color="FF4444", fill_type="solid")
        for row_idx, item in enumerate(failed_files, 2):
            ws.cell(row=row_idx, column=1, value=item["file"])
            ws.cell(row=row_idx, column=2, value=item["reason"])
            ws.cell(row=row_idx, column=3, value=item["timestamp"])
        for col in ws.columns:
            ml = max(len(str(c.value)) if c.value else 0 for c in col)
            ws.column_dimensions[col[0].column_letter].width = ml + 2
        wb.save(logs_dir / "merge_failed.xlsx")
        (logs_dir / "merge_failed.json").write_text(json.dumps(failed_files, indent=2, ensure_ascii=False), encoding="utf-8")
        log(f"[EXPORT] Failed files -> logs/merge_failed.xlsx & .json ({len(failed_files)})")

    if skipped_files:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Skipped Files"
        for col, h in enumerate(["File PDF", "Alasan", "Timestamp"], 1):
            c = ws.cell(row=1, column=col, value=h)
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = PatternFill(start_color="FFA500", end_color="FFA500", fill_type="solid")
        for row_idx, item in enumerate(skipped_files, 2):
            ws.cell(row=row_idx, column=1, value=item["file"])
            ws.cell(row=row_idx, column=2, value=item["reason"])
            ws.cell(row=row_idx, column=3, value=item["timestamp"])
        for col in ws.columns:
            ml = max(len(str(c.value)) if c.value else 0 for c in col)
            ws.column_dimensions[col[0].column_letter].width = ml + 2
        wb.save(logs_dir / "merge_skipped.xlsx")
        (logs_dir / "merge_skipped.json").write_text(json.dumps(skipped_files, indent=2, ensure_ascii=False), encoding="utf-8")
        log(f"[EXPORT] Skipped files -> logs/merge_skipped.xlsx & .json ({len(skipped_files)})")


    # ── Auto-export GAGAL_FALLBACK ──
    export_gagal_fallback(logs_dir, failed_files=failed_files, skipped_files=skipped_files)

    summary = {
        "step": "merge",
        "success": success,
        "failed": failed,
        "skipped": skipped,
        "failed_file": "logs/merge_failed.xlsx" if failed_files else None,
        "skipped_file": "logs/merge_skipped.xlsx" if skipped_files else None,
    }
    print(f"__SUMMARY__:{json.dumps(summary)}", flush=True)
    log(f"\nSelesai. Sukses: {success}, Dilewati: {skipped}, Gagal: {failed}.")
    return 0 if success > 0 or skipped > 0 else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
