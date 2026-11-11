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
import warnings; warnings.filterwarnings("ignore", category=FutureWarning)
try:
    import pymupdf as fitz
except ImportError:
    import fitz
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
    sanitize_segment, determine_btp, _detect_ws_bs_category,
)
from employee_manager import (
    load_pegawai_config, extract_page1_tim1_personnel,
    get_tim2_roster_for_date, get_tim3_roster_for_date, replace_page1_employee_names
)
try:
    from audit_and_correct_personnel import (
        extract_personnel_from_pdf, extract_missing_no_sc, get_roster_sets
    )
except ImportError:
    extract_personnel_from_pdf = None
    extract_missing_no_sc = None
    get_roster_sets = None
from date_changer_engine import _get_date_cell_bounds, _get_date_font

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


_CHECKLIST_CONFIG_CACHE = None

def load_checklist_config(path: str = CHECKLIST_CONFIG_PATH) -> dict:
    global _CHECKLIST_CONFIG_CACHE
    if _CHECKLIST_CONFIG_CACHE is not None:
        return _CHECKLIST_CONFIG_CACHE
    config_candidates = [
        Path(path),
        Path(__file__).resolve().parent / "checklist_types.json",
        Path(__file__).resolve().parent.parent / "config" / "checklist_types.json",
    ]
    for c in config_candidates:
        if c.exists():
            try:
                with open(c, encoding="utf-8") as f:
                    _CHECKLIST_CONFIG_CACHE = json.load(f)
                    return _CHECKLIST_CONFIG_CACHE
            except Exception:
                pass
    _CHECKLIST_CONFIG_CACHE = {"search_keyword": "PERAWATAN", "types": {}}
    return _CHECKLIST_CONFIG_CACHE


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
    """Updates Page 1 date value to match target PDF filename date format, centered inside its table cell."""
    m = re.search(r'(\d{2})-(\d{2})-(\d{4})', filename)
    if not m:
        return

    raw_date = m.group(0)
    parts = raw_date.split('-')
    target_date_ymd = f"{parts[2]}-{parts[1]}-{parts[0]}"

    page1 = doc[0]
    blocks = page1.get_text("dict")["blocks"]
    date_span = None
    fallback_span = None

    for b in blocks:
        if "lines" not in b:
            continue
        for l in b["lines"]:
            for span in l["spans"]:
                txt = span["text"].strip()
                if re.fullmatch(r"\d{4}[-/]\d{2}[-/]\d{2}", txt) or re.fullmatch(r"\d{2}[-/]\d{2}[-/]\d{4}", txt):
                    date_span = span
                    break
                if fallback_span is None and span["bbox"][1] < 350 and ("2025" in txt or "2026" in txt) and ("-" in txt or "/" in txt or " " in txt):
                    fallback_span = span
            if date_span:
                break
        if date_span:
            break

    if not date_span:
        date_span = fallback_span

    if date_span:
        bbox = fitz.Rect(date_span["bbox"])
        origin = date_span.get("origin")
        original_txt = date_span["text"].strip()
        new_date_text = target_date_ymd if re.match(r'^\d{4}-\d{2}-\d{2}$', original_txt) else raw_date

        x_left, x_right = _get_date_cell_bounds(page1, bbox)
        font_name, font_file = _get_date_font()
        font_size = date_span.get("size", 7.8) or 7.8

        if font_file:
            try:
                custom_font = fitz.Font(fontfile=font_file)
                text_w = custom_font.text_length(new_date_text, fontsize=font_size)
            except Exception:
                text_w = fitz.get_text_length(new_date_text, fontname="hebo", fontsize=font_size)
        else:
            text_w = fitz.get_text_length(new_date_text, fontname="hebo", fontsize=font_size)

        center_x = (x_left + x_right) / 2.0
        insert_x = center_x - (text_w / 2.0)
        origin_y = origin[1] if origin else (bbox.y1 - 1.5)

        # Skip rewriting if already exact text, same font family, and centered
        if original_txt == new_date_text and abs(bbox.x0 - insert_x) < 1.0 and "DejaVu" in date_span.get("font", ""):
            return

        # Redact strictly inside cell bounds so border lines remain untouched
        clean_x0 = max(x_left + 0.5, min(bbox.x0, insert_x) - 0.8)
        clean_x1 = min(x_right - 0.5, max(bbox.x1, insert_x + text_w) + 0.8)
        redact_rect = fitz.Rect(clean_x0, bbox.y0 - 0.8, clean_x1, bbox.y1 + 0.8)
        page1.add_redact_annot(redact_rect, fill=(1, 1, 1))
        page1.apply_redactions()

        insert_kwargs = {
            "fontsize": font_size,
            "fontname": font_name if font_file else "hebo",
            "color": (0, 0, 0)
        }
        if font_file:
            insert_kwargs["fontfile"] = font_file

        page1.insert_text((insert_x, origin_y), new_date_text, **insert_kwargs)


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


ASSET_LOCATION_MAP = {}

def load_asset_location_mapping(photos_dir: Path = None, logs_dir: Path = Path("logs")) -> dict:
    global ASSET_LOCATION_MAP
    if ASSET_LOCATION_MAP:
        return ASSET_LOCATION_MAP
    candidates = []
    if photos_dir:
        candidates.extend([
            photos_dir / "asset_location_mapping.json",
            photos_dir.parent / "asset_location_mapping.json",
            photos_dir.parent / "logs" / "asset_location_mapping.json",
        ])
    candidates.extend([
        logs_dir / "asset_location_mapping.json",
        Path("logs/asset_location_mapping.json"),
        Path("02_server_update/logs/asset_location_mapping.json"),
    ])
    for c in candidates:
        if c.is_file():
            try:
                ASSET_LOCATION_MAP = json.loads(c.read_text(encoding="utf-8"))
                return ASSET_LOCATION_MAP
            except Exception:
                pass
    return ASSET_LOCATION_MAP

def get_identifier_candidates(identifier: str) -> list[str]:
    """Expand identifier to account for compound stations, aliases, spacing variants, and known exceptions."""
    cands = [identifier]
    # Check asset_location_mapping
    a_map = ASSET_LOCATION_MAP.get("asset_to_location", {})
    if identifier in a_map:
        mapped_loc = a_map[identifier]
        if mapped_loc not in cands:
            cands.append(mapped_loc)

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

    if identifier == "J12B MSG":
        cands.append("J12 MSG")
    elif identifier == "J12 MSG":
        cands.append("J12B MSG")

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

        # Fallback to station code if identifier contains station code
    codes = re.findall(r'\b(BOO|CLT|BJD|BOP|BTT|CGB|CS|COS|MSG|CCR)\b', identifier, re.I)
    if codes:
        st_code = "COS" if codes[0].upper() == "CS" else codes[0].upper()
        if st_code not in cands:
            cands.append(st_code)

    return list(dict.fromkeys(cands))


def _find_candidate_folders(base_dir: Path, cand: str, expected_suffix: str = "") -> list[Path]:
    """Find matching subfolders for cand, supporting exact match, suffix (_DD-MM atau _DD-MM-YYYY), and space-insensitive matching."""
    if not base_dir.is_dir():
        return []
    suffixes = [expected_suffix] if isinstance(expected_suffix, str) else list(expected_suffix or [])
    suffixes = [s for s in suffixes if s]

    folders = []
    for suf in suffixes:
        suf_p = base_dir / f"{cand}{suf}"
        if suf_p.is_dir() and suf_p not in folders:
            folders.append(suf_p)
    exact_p = base_dir / cand
    if exact_p.is_dir() and exact_p not in folders:
        folders.append(exact_p)

    cand_clean = re.sub(r'_\d{2}-\d{2}(?:-\d{4})?(?:_part\d+)?$', '', cand).replace(" ", "").upper()
    suf_cleans = [f"{cand_clean}{s.replace(' ', '').upper()}" for s in suffixes]
    base_fallback = []
    target_dd = None
    if suffixes:
        m_dd = re.search(r'_(\d{2})-\d{2}', suffixes[0])
        if m_dd:
            target_dd = int(m_dd.group(1))
    try:
        for sub in base_dir.iterdir():
            if sub.is_dir() and sub not in folders:
                sub_clean = sub.name.replace(" ", "").upper()
                if (suf_cleans and sub_clean in suf_cleans) or (sub_clean == cand_clean):
                    folders.append(sub)
                else:
                    sub_base = re.sub(r'_\d{2}-\d{2}(?:-\d{4})?(?:_PART\d+)?$', '', sub_clean, flags=re.I)
                    if sub_base == cand_clean:
                        sub_dd = 999
                        m_sdd = re.search(r'_(\d{2})-\d{2}', sub.name)
                        if m_sdd and target_dd is not None:
                            sub_dd = abs(int(m_sdd.group(1)) - target_dd)
                        base_fallback.append((sub_dd, sub))
    except Exception:
        pass
    if not folders and base_fallback:
        base_fallback.sort(key=lambda x: x[0])
        folders.extend([ item[1] for item in base_fallback ])
    return folders


def _build_tim1_pool_for_date(
    date_key: str,
    k_counts: Counter,
    p_counts: Counter,
    pegawai_config: dict,
    kaur_map: dict,
    pnc_map: dict,
) -> dict:
    """Resolve consistent (1 KAUR, 2 PNC) Tim 1 fallback pool for date_key."""
    all_k = list(pegawai_config.get("kaur", []))
    all_p = list(pegawai_config.get("pnc", []))
    k_ord = {k["nama"].strip().upper(): idx for idx, k in enumerate(all_k)}
    p_ord = {p["nama"].strip().upper(): idx for idx, p in enumerate(all_p)}

    m_day = re.match(r'^(\d{2})', str(date_key).strip())
    day_num = int(m_day.group(1)) if m_day else 1

    k_sorted = sorted(k_counts.keys(), key=lambda n: (-k_counts[n], k_ord.get(n, 999)))
    p_sorted = sorted(p_counts.keys(), key=lambda n: (-p_counts[n], p_ord.get(n, 999)))

    chosen_k = [kaur_map[n] for n in k_sorted[:1] if n in kaur_map]
    chosen_p = [pnc_map[n] for n in p_sorted[:2] if n in pnc_map]

    if not chosen_k and all_k:
        chosen_k.append(all_k[(day_num - 1) % len(all_k)])

    while len(chosen_p) < 2 and len(chosen_p) < len(all_p):
        p_shift = ((day_num - 1) * 2 + len(chosen_p)) % len(all_p)
        cand = all_p[p_shift]
        if cand not in chosen_p:
            chosen_p.append(cand)
        else:
            for p in all_p:
                if p not in chosen_p:
                    chosen_p.append(p)
                    break

    return {
        "kaur": chosen_k,
        "pnc": chosen_p,
        "tokens": {x["nama"] for x in (chosen_k + chosen_p)},
    }


def _auto_correct_tim1_page1_if_needed(
    doc: fitz.Document,
    date_key: str,
    pegawai_config: dict | None,
    tim1_pool_by_date: dict | None,
    _log,
) -> None:
    """Koreksi otomatis Halaman 1 Tim 1 jika defisit (< 1 KAUR / < 2 PNC), ada non-teknisi, atau No. SC kosong."""
    if not extract_personnel_from_pdf or not get_roster_sets:
        return
    cfg = pegawai_config or load_pegawai_config()
    kaur_map, pnc_map, cfg = get_roster_sets(cfg)
    all_k = list(cfg.get("kaur", []))
    all_p = list(cfg.get("pnc", []))
    if not all_k or len(all_p) < 2:
        return

    found_k, found_p, raw_personnel, unauth = extract_personnel_from_pdf(
        doc, kaur_map, pnc_map, return_unauthorized=True
    )
    if raw_personnel and not found_k and not found_p:
        for raw_name in raw_personnel:
            norm = re.sub(r'\s+', ' ', raw_name).strip().upper()
            if norm in kaur_map and kaur_map[norm] not in found_k:
                found_k.append(kaur_map[norm])
            elif norm in pnc_map and pnc_map[norm] not in found_p:
                found_p.append(pnc_map[norm])

    num_k, num_p = len(found_k), len(found_p)
    if num_k < 1 or num_p < 2 or bool(unauth):
        pool = (tim1_pool_by_date or {}).get(date_key) or _build_tim1_pool_for_date(
            date_key, Counter(), Counter(), cfg, kaur_map, pnc_map
        )
        chosen_kaur = found_k[0] if found_k else pool["kaur"][0]
        chosen_pnc = list(found_p[:2])
        seen_p_names = {p["nama"].strip().upper() for p in chosen_pnc}
        for cand_pool in (pool["pnc"], all_p):
            for p_obj in cand_pool:
                if len(chosen_pnc) >= 2:
                    break
                p_name_u = p_obj["nama"].strip().upper()
                if p_name_u not in seen_p_names:
                    chosen_pnc.append(p_obj)
                    seen_p_names.add(p_name_u)
            if len(chosen_pnc) >= 2:
                break

        if len(chosen_pnc) < 2:
            return

        new_roster = [chosen_kaur, chosen_pnc[0], chosen_pnc[1]]
        ok_rep = replace_page1_employee_names(doc, new_roster, sc_only=False)
        reason = f"non-teknisi ({', '.join(unauth)})" if unauth else f"{num_k} KAUR, {num_p} PNC"
        if ok_rep:
            _log(
                f"  │   ├── 👤 [KOREKSI PERSONIL] {reason} -> 1 KAUR, 2 PNC "
                f"({chosen_kaur['nama']}, {chosen_pnc[0]['nama']}, {chosen_pnc[1]['nama']})"
            )
        else:
            _log(f"  │   ├── ⚠️ [WARNING PERSONIL] Gagal koreksi tabel Halaman 1 ({reason})")
        return

    # Sudah >= 1 KAUR, >= 2 PNC tanpa non-teknisi: pertahankan nama, lengkapi No. SC jika ada yang kosong
    if extract_missing_no_sc and raw_personnel:
        missing_sc = extract_missing_no_sc(doc, raw_personnel, kaur_map, pnc_map)
        if missing_sc:
            if replace_page1_employee_names(doc, found_k + found_p, sc_only=True):
                _log(f"  │   ├── 🧾 [LENGKAPI NO. SC] Diperbarui untuk {len(missing_sc)} personil")


def process_pdf(pdf_path: Path, photos_dir: Path, output_dir: Path,
                 input_root: Path | None = None,
                 sap_mapping: dict | None = None,
                 schedule_map: dict | None = None,
                 tim2_roster_cache: dict | None = None,
                 tim1_personnel_by_date: dict | None = None,
                 pegawai_config: dict | None = None,
                 log_fn=None,
                 split_multi_asset: bool = False,
                 tim1_pool_by_date: dict | None = None) -> str:
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

    if category in ("UNKNOWN", "PTLS") and page1_text:
        ws_bs_p1 = _detect_ws_bs_category(page1_text)
        if ws_bs_p1:
            category = ws_bs_p1

    date_str = extract_date_from_page1(page1_text)
    fn_date_str = format_date_from_filename(pdf_path.name)
    if fn_date_str:
        date_str = fn_date_str
    checklist_title = extract_checklist_title(page1_text, pdf_path.name, config)

    # Scan ALL funclocs on page 1
    all_funclocs = extract_all_funclocs(page1_text)
    _log(f"  ├── Funclocs : {len(all_funclocs)} aset pada dokumen")
    load_asset_location_mapping(photos_dir)

    MULTI_ROW_CATEGORIES = {"SINYAL", "WESEL", "AXC"}
    is_multi_row_cat = category in MULTI_ROW_CATEGORIES

    asset_entries = []
    seen = set()

    if split_multi_asset and not is_multi_row_cat and len(all_funclocs) > 1:
        # Bagi Foto & Jam Sesuai Jumlah Baris Aset:
        # Buat entri terpisah untuk SETIAP baris funcloc, mengacu pada folder foto lokasi
        for idx, funcloc_line in enumerate(all_funclocs):
            fl_clean = funcloc_line.strip()
            parts = fl_clean.split(":", 1)
            asset_title = parts[1].strip() if len(parts) > 1 else fl_clean
            asset_title = re.sub(r'\s+', ' ', asset_title)

            entry_id = f"{asset_title}#{idx}" if asset_title in seen else asset_title
            seen.add(entry_id)
            identifier_to_line[entry_id] = fl_clean

            loc_id = extract_identifier(funcloc_line, category) or extract_station_from_filename(pdf_path.name)
            btp = determine_btp_from_identifier(loc_id or asset_title, pdf_path.name)
            if btp == "UNKNOWN":
                btp = "BTP JAK"
            asset_entries.append((entry_id, btp, category, loc_id))
            _log(f"  │   ├── [{category}] Baris #{idx+1}: {asset_title} -> Lokasi Foto: {loc_id} (Wilayah: {btp})")
    else:
        for funcloc_line in all_funclocs:
            identifier = extract_identifier(funcloc_line, category)
            if identifier and identifier not in seen:
                seen.add(identifier)
                identifier_to_line[identifier] = funcloc_line.strip()
                btp = determine_btp_from_identifier(identifier, pdf_path.name)
                if btp == "UNKNOWN":
                    btp = "BTP JAK"
                photo_category = category
                if category == "UNKNOWN":
                    txt = funcloc_line.strip().upper()
                    if txt.startswith("WSL"): photo_category = "WESEL"
                    elif txt.startswith("SIN"): photo_category = "SINYAL"
                    elif txt.startswith("AXL"): photo_category = "AXC"
                asset_entries.append((identifier, btp, photo_category, identifier))
                _log(f"  │   ├── [{photo_category}] {identifier} (Wilayah: {btp})")
    
    if not asset_entries:
        # Fallback 1: check schedule_map for this PDF
        if schedule_map and pdf_path.name in schedule_map:
            s_entry = schedule_map[pdf_path.name]
            s_id = s_entry.get("identifier")
            s_cat = s_entry.get("category") or category
            s_btp = s_entry.get("btp") or determine_btp_from_identifier(s_id, pdf_path.name)
            if s_id:
                asset_entries.append((s_id, s_btp, s_cat, s_id))
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
                    asset_entries.append((t_id, t_btp, t_cat or category, t_id))
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
            asset_entries.append((identifier, btp, category, identifier))
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

    # Expected date suffix for multi-date / 2x monthly inspections if any
    expected_suffix = []
    m_wsl = re.search(r'(\d{2})-(\d{2})-(\d{4})', pdf_path.name)
    if m_wsl:
        part_m = re.search(r'\((2|3|4)\)', pdf_path.name)
        part_s = f"_part{part_m.group(1)}" if part_m else ""
        expected_suffix = [
            f"_{m_wsl.group(1)}-{m_wsl.group(2)}-{m_wsl.group(3)}{part_s}",
            f"_{m_wsl.group(1)}-{m_wsl.group(2)}{part_s}",
        ]

    MULTI_ROW_CATEGORIES = {"SINYAL", "WESEL", "AXC"}
    is_multi_row = (category in MULTI_ROW_CATEGORIES) or any(item[2] in MULTI_ROW_CATEGORIES for item in asset_entries)

    for item in asset_entries:
        identifier, btp, photo_category, loc_id = item[0], item[1], item[2], item[3] if len(item) > 3 else None

        if not is_multi_row and not split_multi_asset and photo_paths:
            # Opsi A: Untuk kategori non-multi-row (PTLS, CATUDAYA, PDSE, dll.),
            # jika sudah menemukan foto untuk 1 aset (1 baris), batasi agar hanya merender 1 baris foto per PDF.
            break

        found = False
        candidates = get_identifier_candidates(identifier)
        if loc_id:
            loc_cands = get_identifier_candidates(loc_id)
            if split_multi_asset:
                # Prioritaskan folder foto nama spesifik aset (misal: 'OTB 1 ER BOGOR'),
                # dan jadikan variasi loc_id ('JPL 28 BOO', 'ER SINYAL BOO') sebagai cadangan di akhir
                for lc in loc_cands:
                    if lc not in candidates:
                        candidates.append(lc)
            else:
                for lc in reversed(loc_cands):
                    if lc not in candidates:
                        candidates.insert(0, lc)

        # Fallback tambahan: variasi lokasi / identifier dari nama berkas PDF target
        fn_loc = extract_location_from_filename(pdf_path.name) or extract_identifier(pdf_path.name, category)
        if fn_loc:
            for fc in get_identifier_candidates(fn_loc):
                if fc not in candidates:
                    candidates.append(fc)

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

    # Jika split_multi_asset aktif dan ada aset yang belum punya foto, duplikat foto dari aset pertama yang berhasil ditemukan
    if split_multi_asset and photo_paths:
        first_found_photos = list(photo_paths.values())[0]
        first_found_tim = list(photo_tims.values())[0]
        for item in asset_entries:
            identifier = item[0]
            if identifier not in photo_paths:
                photo_paths[identifier] = first_found_photos
                photo_tims[identifier] = first_found_tim
                _log(f"  │   ├── 📷 Foto duplikasi [{identifier}]: diduplikasi dari baris pertama")
    
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

    # ── Update employee names on Page 1 (Tim 2/3 full roster; Tim 1 deficit/SC auto-fix) ──
    m_date_p1 = re.search(r'(\d{2})-(\d{2})-(\d{4})', pdf_path.name)
    d_key_p1 = m_date_p1.group(0) if m_date_p1 else date_str
    if output_tim == "Tim_2":
        if tim2_roster_cache is not None:
            if d_key_p1 not in tim2_roster_cache:
                t1_tokens = tim1_personnel_by_date.get(d_key_p1, set()) if tim1_personnel_by_date else set()
                tim2_roster_cache[d_key_p1] = get_tim2_roster_for_date(d_key_p1, t1_tokens, pegawai_config)
            roster = tim2_roster_cache[d_key_p1]
        else:
            t1_tokens = tim1_personnel_by_date.get(d_key_p1, set()) if tim1_personnel_by_date else set()
            roster = get_tim2_roster_for_date(d_key_p1, t1_tokens, pegawai_config)
        replace_page1_employee_names(doc, roster)
    elif output_tim and output_tim.startswith("Tim_") and output_tim not in ("Tim_1", "Tim_2"):
        roster_t3 = get_tim3_roster_for_date(d_key_p1, pegawai_config)
        replace_page1_employee_names(doc, roster_t3)
    else:
        _auto_correct_tim1_page1_if_needed(
            doc, d_key_p1, pegawai_config, tim1_pool_by_date, _log
        )

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
        doc.save(str(out_pdf_path), garbage=4, deflate=True, clean=True)
    except Exception as save_err:
        try:
            temp_out = out_pdf_path.with_name(f"{out_pdf_path.stem}_tmp_{os.getpid()}{out_pdf_path.suffix}")
            doc.save(str(temp_out), garbage=4, deflate=True, clean=True)
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
    p.add_argument("--schedule", default=None, help="Path ke schedule.json")
    p.add_argument("--split-multi-asset", action="store_true", help="Bagi foto dan jam sesuai jumlah baris aset")
    p.add_argument("--file", default=None, help="Nama atau path berkas PDF spesifik untuk diproses saja")
    p.add_argument("--period-filter", default="", help="Filter periode (misal '01. JANUARI' atau '2025/01. JANUARI')")
    return p.parse_args()


def _merge_worker_wrapper(args_tuple):
    (pdf_path, photos_dir, output_dir, input_dir, sap_mapping, schedule_map,
     tim2_roster_cache, tim1_personnel_by_date, pegawai_config, split_multi_asset,
     tim1_pool_by_date) = args_tuple
    captured_lines = []
    try:
        status = process_pdf(pdf_path, photos_dir, output_dir, input_dir, sap_mapping, schedule_map,
                             tim2_roster_cache, tim1_personnel_by_date, pegawai_config,
                             log_fn=captured_lines.append,
                             split_multi_asset=split_multi_asset,
                             tim1_pool_by_date=tim1_pool_by_date)
    except Exception as exc:
        status = f"failed: exception {exc}"
    return pdf_path, status, captured_lines


def main(override_args=None):
    sap_path = SAP_MAPPING_PATH
    if not Path(sap_path).exists() and Path("config/sap_station_mapping.json").exists():
        sap_path = "config/sap_station_mapping.json"
    sap_mapping = load_sap_mapping(sap_path)

    args = parse_args() if override_args is None else override_args
    input_dir = Path(args.input).resolve()
    photos_dir = Path(args.photos).resolve()
    output_dir = Path(args.output).resolve()

    if override_args is None and not getattr(args, "period_filter", "") and not args.file and not args.schedule and input_dir.is_dir():
        from export_pdf_foto import resolve_pdf_period_map, split_export_base_and_subdir
        EXCLUDE_PRE = {"backups", "backup", "_temp_merged", "05_pdf_merged", "03_export_foto", "03_photos_export", "04_photos_edited", "04_foto_edited", ".git", "node_modules"}
        EXCL_L = {x.lower() for x in EXCLUDE_PRE}
        scan_pdfs = sorted([
            p for p in input_dir.rglob("*.pdf")
            if p.is_file() and not any(x in EXCL_L for x in ([k.lower() for k in p.relative_to(input_dir).parts[:-1]]))
        ])
        pdf_to_pref, multi_month, _ = resolve_pdf_period_map(scan_pdfs)
        if multi_month:
            photos_base, edited_sub = split_export_base_and_subdir(photos_dir, "04_photos_edited")
            prefs = sorted({pdf_to_pref.get(p, "") for p in scan_pdfs if pdf_to_pref.get(p, "")})
            if prefs and any((photos_base / pr / edited_sub).is_dir() or (photos_base / pr / "04_photos_edited").is_dir() for pr in prefs):
                print(f"[PERIODE] Terdeteksi {len(prefs)} periode untuk Merge PDF.", flush=True)
                rc = 0
                for pr in prefs:
                    m_root = photos_base / pr
                    m_photos = m_root / edited_sub
                    if not m_photos.is_dir():
                        m_photos = m_root / "04_photos_edited"
                    sub_args = argparse.Namespace(**vars(args))
                    sub_args.photos = str(m_photos)
                    sub_args.output = str(output_dir / pr)
                    sub_args.schedule = str(m_root / "schedule.json")
                    sub_args.period_filter = pr
                    print(f"\n── Merge Periode: {pr} ──", flush=True)
                    res = main(override_args=sub_args)
                    if res and res != 0:
                        rc = res
                return rc

    # Load schedule.json for team assignment (prioritize --schedule, input_dir)
    schedule_map = {}
    sched_candidates = []
    if args.schedule:
        sched_candidates.append(Path(args.schedule))
    sched_candidates.append(input_dir / "schedule.json")
    sched_path = next((c for c in sched_candidates if c.is_file()), None)
    if sched_path:
        try:
            with open(sched_path, "r", encoding="utf-8") as f:
                s_data = json.load(f)
                for s in s_data.get("schedules", []):
                    if "file" in s:
                        schedule_map[s["file"]] = s
            log(f"[SCHEDULE] Memuat jadwal tim dari: {sched_path} ({len(schedule_map)} berkas)")
        except Exception as e:
            log(f"[WARNING] Cannot load schedule.json: {e}")

    if not input_dir.is_dir():
        print(f"Folder input tidak ditemukan: {input_dir}")
        return 1
    if not photos_dir.is_dir():
        print(f"Folder foto hasil edit tidak ditemukan: {photos_dir}")
        return 1

    ensure_dir(output_dir)

    # Deferred Stamping: Pastikan seluruh foto clean base ter-stamp ke foto target sesuai koordinat meta.json
    try:
        from edit_timemark_ide1 import draw_textbox, BOX_HEIGHT_RATIO, BOX_WIDTH_RATIO
        for clean_p in photos_dir.rglob("*.clean.jpg"):
            stem = clean_p.stem.replace(".clean", "")
            target_p = clean_p.parent / f"{stem}.jpg"
            meta_p = clean_p.parent / "meta.json"
            if meta_p.exists():
                try:
                    m_data = json.loads(meta_p.read_text(encoding="utf-8"))
                    p_info = m_data.get(f"{stem}.jpg", {})
                    d_text = p_info.get("dateText", "")
                    if d_text:
                        yp = p_info.get("yPos", 220)
                        xp = p_info.get("xPos", 14)
                        with Image.open(clean_p) as _cim:
                            _cim = _cim.convert("RGB")
                            _w, _h = _cim.size
                            _y1 = int((yp / 300.0) * _h) if yp <= 300 else yp
                            _x1 = int((xp / 300.0) * _w) if xp <= 300 else xp
                            _bh = max(10, int(_h * BOX_HEIGHT_RATIO))
                            _bw = max(20, int(_w * BOX_WIDTH_RATIO))
                            _box = (_x1, _y1, min(_w, _x1 + _bw), min(_h, _y1 + _bh))
                            _out = draw_textbox(_cim, _box, d_text, no_bg=True)
                            _out.save(target_p, quality=95, subsampling=0)
                except Exception:
                    pass
    except Exception:
        pass

    EXCLUDE_DIRS = {"backups", "backup", "_temp_merged", "05_pdf_merged", "03_export_foto", "03_photos_export", "04_photos_edited", "04_foto_edited", ".git", "node_modules"}
    EXCLUDE_LOWER = {x.lower() for x in EXCLUDE_DIRS}
    def _is_sub_excluded(p: Path, base: Path) -> bool:
        try:
            sub_parts = [x.lower() for x in p.relative_to(base).parts[:-1]]
        except Exception:
            sub_parts = [x.lower() for x in p.parts[:-1]]
        return any(x in EXCLUDE_LOWER for x in sub_parts)

    pdf_files = sorted([p for p in input_dir.rglob("*.pdf")
                        if not _is_sub_excluded(p, input_dir) and p.is_file()])
    period_filter = (getattr(args, "period_filter", "") or "").strip().replace("\\", "/")
    if period_filter and pdf_files:
        from export_pdf_foto import resolve_pdf_period_map
        pdf_to_pref, _, _ = resolve_pdf_period_map(pdf_files)
        pdf_files = [p for p in pdf_files if pdf_to_pref.get(p, "").replace("\\", "/") == period_filter]
    if not pdf_files:
        print(f"Tidak ada berkas PDF di: {input_dir}")
        return 0

    all_period_pdfs = list(pdf_files)
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
    tim1_pool_by_date = {}
    tim2_roster_cache = {}

    if get_roster_sets:
        _km, _pm, _ = get_roster_sets(pegawai_config)
    else:
        _km, _pm = {}, {}

    _t1_k_counts = defaultdict(Counter)
    _t1_p_counts = defaultdict(Counter)
    _all_t1_dates = set()
    _scan_dates_needed = None
    if args.file:
        _scan_dates_needed = {
            (m.group(0) if (m := re.search(r'(\d{2})-(\d{2})-(\d{4})', p.name)) else "DEFAULT")
            for p in pdf_files
        }
    for p in all_period_pdfs:
        assigned_tim_num = schedule_map.get(p.name, {}).get("tim", 1)
        if assigned_tim_num == 1:
            m_dt = re.search(r'(\d{2})-(\d{2})-(\d{4})', p.name)
            d_k = m_dt.group(0) if m_dt else "DEFAULT"
            if _scan_dates_needed is not None and d_k not in _scan_dates_needed:
                continue
            _all_t1_dates.add(d_k)
            try:
                with fitz.open(str(p)) as doc_scan:
                    if extract_personnel_from_pdf:
                        fk, fp, _ = extract_personnel_from_pdf(doc_scan, _km, _pm)
                        for k_obj in fk:
                            _t1_k_counts[d_k][k_obj["nama"]] += 1
                        for p_obj in fp:
                            _t1_p_counts[d_k][p_obj["nama"]] += 1
                    else:
                        t1_toks = extract_page1_tim1_personnel(doc_scan)
                        if t1_toks:
                            tim1_personnel_by_date[d_k].update(t1_toks)
            except Exception:
                pass

    if extract_personnel_from_pdf:
        for d_k in _all_t1_dates:
            pool = _build_tim1_pool_for_date(
                d_k, _t1_k_counts[d_k], _t1_p_counts[d_k], pegawai_config, _km, _pm
            )
            tim1_pool_by_date[d_k] = pool
            tim1_personnel_by_date[d_k].update(pool["tokens"])

    success = 0
    skipped = 0
    failed = 0
    failed_files = []
    skipped_files = []

    import concurrent.futures

    max_workers = min(len(pdf_files), 4 if args.file else min(12, max(4, (os.cpu_count() or 4) * 2)))
    split_multi_asset = bool(getattr(args, "split_multi_asset", False))
    tasks = [
        (p, photos_dir, output_dir, input_dir, sap_mapping, schedule_map,
         tim2_roster_cache, tim1_personnel_by_date, pegawai_config, split_multi_asset,
         tim1_pool_by_date)
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
                                ok_c, msg_c = apply_core_correction(m_pdf, make_backup=False)
                                log(f"  └── [CORE OPTIK] {msg_c} -> [{c_info['target_core']}]")
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
    # Hapus cache audit lama agar tab Koreksi Dokumen langsung menampilkan status terbaru
    try:
        app_d = os.environ.get("LOCALAPPDATA", "")
        if app_d:
            c_f = Path(app_d) / "SintelisUtility" / "audit_personnel_cache.json"
            if c_f.is_file():
                c_f.unlink()
    except Exception:
        pass

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
