"""extract_pdf_dates.py — Ekstrak tanggal dari filename PDF 2025 (02_pdf_target)
dan tulis date.txt ke folder foto 03_photos_export.

v3 (2026-07-15): Filename-based matching. Parse date/category/identifier
langsung dari nama file. Pdfplumber fallback untuk format lama.
"""
import argparse
import datetime
import os
import re
import sys
import json
import shutil
from pathlib import Path
from collections import defaultdict

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import pdfplumber

from export_pdf_foto import (
    extract_all_funclocs, 
    extract_identifier, 
    normalize_jpl_identifier, 
    STATION_TO_BTP
)

DEFAULT_PDF_DIR = "./02_pdf_target"
DEFAULT_OUTPUT_ROOT = "./03_photos_export"

INDONESIAN_DAYS = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
INDONESIAN_MONTHS = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "Mei", 6: "Jun",
    7: "Jul", 8: "Agt", 9: "Sep", 10: "Okt", 11: "Nov", 12: "Des"
}

# ── Filename category keyword → Export folder category name ──
FILENAME_TO_CATEGORY = {
    "AXLE COUNTER": "AXC",
    "CATU DAYA": "CATUDAYA",
    "PINTU PERLINTASAN": "PINTU_PERLINTASAN",
    "SERAT OPTIK": "SERAT OPTIK",
    "SINYAL": "SINYAL",
    "WESEL": "WESEL",
    "PTPP": "PTPP",
    "CTS": "CTS",
    "PDSE": "PDSE",
    "PTDS": "PTDS",
    "PTLS": "PTLS",
    "TELEKOMUNIKASI": "TELEKOMUNIKASI",
    "CTC-CTS": "CTS",
    "POINT LOCK": "WESEL",
}
# Ordered longest-first for greedy matching
_CATEGORY_KEYWORDS = sorted(FILENAME_TO_CATEGORY.keys(), key=len, reverse=True)

# ── Identifier exceptions (target filename → export folder) ──
IDENTIFIER_EXCEPTIONS = {
    "ZP 41B": "ZP 41",  # Typo in original PDF target
    "JPL 26": "JPL 26N",  # Filename sengaja tanpa N, aset aslinya 26N
}

# ── Station aliases (filename station → export folder station) ──
STATION_ALIASES = {
    "COS": "CIOMAS",  # Cilebut/Cigombong
    "CIOMAS": "COS",  # reverse
    "ER SINYAL": "ER",  # ER SINYAL CLT -> ER CLT
    "ER TELKOM": "ER RADIO",  # ER TELKOM CIOMAS -> ER RADIO CIOMAS
    "ER RADIO": "ER TELKOM",  # reverse
}

# ── Category aliases (when folders are in different category) ──
# JPL folder bisa di PTPP, PTPP folder bisa di JPL
CATEGORY_ALIASES = {
    "JPL": ["PTPP"],
    "PTPP": ["JPL"],
}

MONTH_MAP = {
    "januari": 1, "jan": 1, "februari": 2, "feb": 2,
    "maret": 3, "mar": 3, "april": 4, "apr": 4,
    "mei": 5, "may": 5, "juni": 6, "jun": 6,
    "juli": 7, "jul": 7, "agustus": 8, "agt": 8, "aug": 8,
    "september": 9, "sep": 9, "oktober": 10, "okt": 10,
    "november": 11, "nov": 11, "desember": 12, "des": 12
}


def parse_date_indonesian(text: str) -> datetime.date | None:
    """Parse date from Indonesian text (fallback for old-format PDFs)."""
    # 1. DD Bulan YYYY
    pattern = re.compile(
        r"(\d{1,2})\s+(januari|februari|maret|april|mei|juni|juli|agustus|september|oktober|november|desember|jan|feb|mar|apr|jun|jul|agt|aug|sep|okt|nov|des)\s+(\d{4})",
        re.IGNORECASE
    )
    match = pattern.search(text)
    if match:
        day = int(match.group(1))
        month_str = match.group(2).lower()
        year = int(match.group(3))
        month = MONTH_MAP.get(month_str)
        if month:
            try:
                return datetime.date(year, month, day)
            except ValueError:
                pass

    # 2. YYYY-MM-DD
    iso_pattern = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
    match = iso_pattern.search(text)
    if match:
        try:
            return datetime.date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            pass

    # 3. DD-MM-YYYY
    dd_pattern = re.compile(r"(\d{2})-(\d{2})-(\d{4})")
    match = dd_pattern.search(text)
    if match:
        try:
            return datetime.date(int(match.group(3)), int(match.group(2)), int(match.group(1)))
        except ValueError:
            pass

    return None


def format_date_target(dt: datetime.date) -> str:
    day_name = INDONESIAN_DAYS[dt.weekday()]
    month_name = INDONESIAN_MONTHS[dt.month]
    return f"{day_name}, {month_name} {dt.day:02d} {dt.year}"


def parse_date_from_filename(date_str: str) -> datetime.date | None:
    """Parse DD-MM-YYYY string → date object."""
    m = re.match(r'^(\d{2})-(\d{2})-(\d{4})$', date_str)
    if not m:
        return None
    try:
        return datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def parse_target_filename(filename: str) -> tuple[str, str, str] | None:
    """Parse 'PERAWATAN TYPE ID STATION DD-MM-YYYY.pdf' → (category, identifier, date_str).
    
    Returns None if filename doesn't match expected format.
    """
    stem = Path(filename).stem  # Remove .pdf
    # Fix double .pdf.pdf
    if stem.lower().endswith('.pdf'):
        stem = stem[:-4]
    # Strip trailing (N) duplicate suffix
    stem = re.sub(r'\s*\(\d+\)\s*$', '', stem)

    # Match: PERAWATAN {asset_part} DD-MM-YYYY
    m = re.match(r'^PERAWATAN\s+(.+?)\s+(\d{2}-\d{2}-\d{4})$', stem)
    if not m:
        return None

    asset_part = m.group(1).strip()
    date_str = m.group(2)

    # Find category keyword (longest match first)
    category = None
    identifier = None
    for kw in _CATEGORY_KEYWORDS:
        if asset_part.startswith(kw + ' '):
            category = FILENAME_TO_CATEGORY[kw]
            identifier = asset_part[len(kw):].strip()
            break

    if not category or not identifier:
        return None

    # Apply identifier exceptions (exact identifier match, not substring)
    # e.g. "JPL 26" → "JPL 26N" should NOT turn "JPL 26N CLT" into "JPL 26NN CLT"
    ident_exact = identifier  # e.g. "JPL 26 CLT"
    for old, new in IDENTIFIER_EXCEPTIONS.items():
        # Match exact identifier or same prefix (first 2 tokens match)
        tokens = identifier.split()
        old_tokens = old.split()
        if len(tokens) >= len(old_tokens) and tokens[:len(old_tokens)] == old_tokens:
            rest = ' '.join(tokens[len(old_tokens):])
            identifier = f"{new} {rest}".strip() if rest else new

    # ── CATUDAYA: map filename identifier → export folder identifier ──
    # "ER SINYAL BOO" → "BOO", "ER SINYAL CLT" → "CLT", "ER RADIO BOO" → "RADIO_BOO"
    if category == "CATUDAYA":
        for prefix in ["ER SINYAL ", "ER RADIO "]:
            if identifier.startswith(prefix):
                code = identifier[len(prefix):].strip()
                identifier = f"RADIO_{code}" if prefix == "ER RADIO " else code
                break

    # ── SERAT OPTIK: strip "OTB " prefix and map "BOO" / "BOGOR" / "RUANG RADIO BOGOR" -> "RUANG RADIO BOO" ──
    if category == "SERAT OPTIK":
        if identifier.startswith("OTB "):
            identifier = identifier[4:].strip()
        if identifier in ("BOO", "BOGOR", "RUANG RADIO BOGOR"):
            identifier = "RUANG RADIO BOO"

    # ── PINTU_PERLINTASAN: map category to JPL (folder export pake JPL)
    # dan normalisasi identifier
    if category == "PINTU_PERLINTASAN":
        category = "JPL"
        # Strip "ELEKTRIK" dari "JPL ELEKTRIK BNR BOP - BTT"
        identifier = re.sub(r'\s*ELEKTRIK\s*', ' ', identifier).strip()
        # Normalize " - " (space-dash-space) → "-" biar _alternate_ids cocok
        identifier = identifier.replace(' - ', '-')

    return (category, identifier, date_str)


def _has_jpg(d: Path) -> bool:
    try:
        with os.scandir(d) as entries:
            for entry in entries:
                if entry.name.lower().endswith(".jpg"):
                    return True
    except OSError:
        pass
    return False


def extract_date_from_pdf(pdf_path) -> datetime.date | None:
    """Fallback: read date from PDF page 1 via PyMuPDF fitz with pdfplumber fallback."""
    try:
        import fitz
        with fitz.open(str(pdf_path)) as doc:
            if len(doc) > 0:
                t = doc[0].get_text() or ""
                dt = parse_date_indonesian(t)
                if dt:
                    return dt
    except Exception:
        pass
    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            if not pdf.pages:
                return None
            return parse_date_indonesian(pdf.pages[0].extract_text() or "")
    except Exception:
        return None


def build_folder_lookup(output_root: Path) -> dict[tuple[str, str], list[Path]]:
    """Pre-scan 03_photos_export/ → {(category, identifier): [folder_path]}.
    
    Also adds prefix-based alternate keys for fuzzy matching.
    E.g. folder "JPL 07 BOO-BOP" also gets key "JPL 07 BOO" so filename
    "PERAWATAN SERAT OPTIK JPL 07 BOO ..." can match it.
    """
    lookup = defaultdict(list)
    if not output_root.exists():
        return lookup

    # Station suffixes that funcloc-derived folder names may add
    _STATION_SUFFIXES = ["BOP-BTT", "BOO-BOP", "BJD-CLT", "CLT-BOO", "BOO-CLT",
                         "CCR-MSG", "MSG-BTT", "BTT-MSG", "MSG-CCR", "CLT-BJD"]

    for btp_dir in output_root.iterdir():
        if not btp_dir.is_dir():
            continue
        for cat_dir in btp_dir.iterdir():
            if not cat_dir.is_dir():
                continue
            category = cat_dir.name
            for ident_dir in cat_dir.iterdir():
                if not ident_dir.is_dir():
                    continue
                if _has_jpg(ident_dir):
                    key = (category, ident_dir.name)
                    lookup[key].append(ident_dir)

                    # Strip _DD-MM suffix if present → also map base identifier for any category
                    # e.g. "W13 BOO_02-01" → base "W13 BOO", "B104 CLT-BOO_10-02" → base "B104 CLT-BOO"
                    name = ident_dir.name
                    suf_m = re.match(r'^(.+?)_(\d{2}-\d{2})$', name)
                    if suf_m:
                        base_name = suf_m.group(1)
                        base_key = (category, base_name)
                        if base_key not in lookup:
                            lookup[base_key] = []
                        if ident_dir not in lookup[base_key]:
                            lookup[base_key].append(ident_dir)

                    # Add fuzzy/prefix keys (strip compound station suffixes)
                    # "MJ28 BOP-BTT" -> keys: "MJ28 BOP", "MJ28 BTT", "MJ28"
                    # "JPL 07 BOO-BOP" -> keys: "JPL 07 BOO", "JPL 07 BOP", "JPL 07"
                    for suffix in _STATION_SUFFIXES:
                        if name.endswith(suffix):
                            base = name[:-len(suffix)].strip().rstrip("-").strip()
                            parts = suffix.split("-")
                            if base:
                                # Add each station part as a key
                                for part in parts:
                                    part_key = (category, f"{base} {part}")
                                    if part_key not in lookup:
                                        lookup[part_key] = []
                                    if ident_dir not in lookup[part_key]:
                                        lookup[part_key].append(ident_dir)
                                # Add base-only variant
                                base_key = (category, base)
                                if base_key not in lookup:
                                    lookup[base_key] = []
                                if ident_dir not in lookup[base_key]:
                                    lookup[base_key].append(ident_dir)

                    # Add alias variants (COS <-> CIOMAS etc)
                    for alias_from, alias_to in STATION_ALIASES.items():
                        if alias_from in name:
                            alias_name = name.replace(alias_from, alias_to)
                            alt_key = (category, alias_name)
                            if alt_key not in lookup:
                                lookup[alt_key] = []
                            if ident_dir not in lookup[alt_key]:
                                lookup[alt_key].append(ident_dir)

                    # Add RADIO_ prefix variants: "RADIO_COS" → also key (cat, "COS")
                    if name.startswith("RADIO_"):
                        stripped_name = name[len("RADIO_"):]
                        stripped_key = (category, stripped_name)
                        if stripped_key not in lookup:
                            lookup[stripped_key] = []
                        if ident_dir not in lookup[stripped_key]:
                            lookup[stripped_key].append(ident_dir)

    return lookup


def normalize_identifier(ident: str) -> str:
    """Normalize identifier by sorting multi-station suffixes alphabetically."""
    if not ident:
        return ident
    if ident.startswith("JPL "):
        return normalize_jpl_identifier(ident)
    parts = ident.rsplit(" ", 1)
    if len(parts) == 2:
        base, station = parts
        if "-" in station:
            st_parts = station.split("-")
            st_parts.sort()
            return f"{base} {'-'.join(st_parts)}"
    return ident


def _alternate_ids(identifier: str) -> list[str]:
    """Generate alternate identifiers from compound station suffixes.
    
    E.g. 'UB101 BJD-CLT' -> ['UB101 BJD', 'UB101 CLT']
         'JPL 07 BOO-BOP' -> ['JPL 07 BOO', 'JPL 07 BOP']
    """
    alts = []
    parts = identifier.rsplit(" ", 1)
    if len(parts) == 2:
        base, station = parts
        if "-" in station:
            for p in station.split("-"):
                alts.append(f"{base} {p}")
    return alts


MAPPING_FILE = Path("logs/asset_folder_mapping.json")


def load_folder_mapping(path: Path = MAPPING_FILE) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_folder_mapping(path: Path, mapping: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_text(json.dumps(mapping, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        print(f"[WARNING] Gagal menyimpan {path}: {e}")


def prepare_multi_date_folders(output_root: Path, pdf_files: list[Path], logs_dir: Path = Path("logs")) -> dict:
    """Pre-scan target PDFs, identify assets with multiple dates, and manage suffixed folders.
    - If base folder exists (e.g. B104 CLT-BOO):
        1. Renames base folder to B104 CLT-BOO_{first_date}
        2. Copies to B104 CLT-BOO_{subsequent_dates}
    - If base folder already renamed in earlier run:
        Ensures all subsequent dates have folders copied.
    - Saves mapping to logs/asset_folder_mapping.json.
    """
    mapping = load_folder_mapping(logs_dir / "asset_folder_mapping.json")
    
    # 1. Pre-scan PDF targets to find dates per asset
    print("[*] Pre-scanning target PDFs untuk mendeteksi aset tanggal ganda...", flush=True)
    asset_dates = defaultdict(lambda: defaultdict(dict))
    
    for pdf_path in pdf_files:
        fname = pdf_path.name
        parsed = parse_target_filename(fname)
        base_category = None
        base_identifier = None
        dt = None
        
        if parsed:
            base_category, base_identifier, date_str = parsed
            dt = parse_date_from_filename(date_str)
        if not dt:
            dt = extract_date_from_pdf(pdf_path)
        if not dt:
            continue
            
        date_suf = dt.strftime("%d-%m")
        date_fmt = format_date_target(dt)
        
        all_funclocs = []
        if not parsed or base_category in {"AXC", "WESEL", "SINYAL"}:
            try:
                import fitz
                with fitz.open(str(pdf_path)) as doc:
                    if len(doc) > 0:
                        text = doc[0].get_text() or ""
                        all_funclocs = extract_all_funclocs(text)
            except Exception:
                pass
                
        idents = []
        if all_funclocs and base_category:
            for fl in all_funclocs:
                ident = extract_identifier(fl, base_category)
                if ident:
                    for old, new in IDENTIFIER_EXCEPTIONS.items():
                        tokens = ident.split()
                        old_tokens = old.split()
                        if len(tokens) >= len(old_tokens) and tokens[:len(old_tokens)] == old_tokens:
                            rest = ' '.join(tokens[len(old_tokens):])
                            ident = f"{new} {rest}".strip() if rest else new
                    norm = normalize_identifier(ident)
                    idents.append((base_category, norm, ident))
        if not idents and base_category and base_identifier:
            norm = normalize_identifier(base_identifier)
            idents.append((base_category, norm, base_identifier))
            
        seen_in_file = set()
        for cat, norm_id, orig_id in idents:
            if orig_id in seen_in_file:
                continue
            seen_in_file.add(orig_id)
            if cat == "PINTU_PERLINTASAN":
                cat = "JPL"
            asset_dates[(cat, orig_id)][date_suf] = {"date": date_fmt, "pdf": fname, "norm": norm_id}

    # 2. Filter multi-date assets
    multi_date_assets = {k: v for k, v in asset_dates.items() if len(v) > 1}
    print(f"[*] Terdeteksi {len(multi_date_assets)} aset memiliki tanggal ganda pada target PDF.", flush=True)

    # 3. For each multi-date asset, check and manage folders in output_root
    btp_dirs = [d for d in output_root.iterdir() if d.is_dir() and d.name.startswith("BTP")]
    if not btp_dirs:
        btp_dirs = [output_root]

    for (cat, orig_id), date_map in multi_date_assets.items():
        sorted_sufs = sorted(date_map.keys())
        first_suf = sorted_sufs[0]
        
        for btp_dir in btp_dirs:
            cat_dir = btp_dir / cat if btp_dir != output_root else output_root / cat
            if not cat_dir.is_dir():
                continue
                
            base_folder = cat_dir / orig_id
            norm_id = list(date_map.values())[0].get("norm", orig_id)
            if not base_folder.is_dir() and (cat_dir / norm_id).is_dir():
                base_folder = cat_dir / norm_id
                
            first_suffixed = cat_dir / f"{orig_id}_{first_suf}"
            if not first_suffixed.is_dir() and (cat_dir / f"{norm_id}_{first_suf}").is_dir():
                first_suffixed = cat_dir / f"{norm_id}_{first_suf}"

            # If base folder exists (from fresh Step 1 export):
            if base_folder.is_dir():
                if first_suffixed.exists() and first_suffixed != base_folder:
                    try:
                        shutil.rmtree(first_suffixed)
                    except Exception:
                        pass
                base_folder.rename(first_suffixed)
                print(f"  [STEP 2] Rename folder dasar: {base_folder.name} -> {first_suffixed.name}", flush=True)
            
            # Now, if first_suffixed exists, ensure all subsequent dates have copies
            if first_suffixed.is_dir():
                for next_suf in sorted_sufs[1:]:
                    next_suffixed = cat_dir / f"{orig_id}_{next_suf}"
                    if not next_suffixed.exists():
                        shutil.copytree(first_suffixed, next_suffixed)
                        print(f"  [STEP 2] Salin foto tanggal ganda: {first_suffixed.name} -> {next_suffixed.name}", flush=True)
                        
                # Update mapping
                map_key = f"{btp_dir.name}/{cat}/{orig_id}"
                mapping[map_key] = {
                    "btp": btp_dir.name,
                    "category": cat,
                    "base_identifier": orig_id,
                    "dates": sorted_sufs,
                    "folders": {suf: f"{orig_id}_{suf}" for suf in sorted_sufs}
                }
                break

    save_folder_mapping(logs_dir / "asset_folder_mapping.json", mapping)
    return mapping


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ekstrak tanggal dari filename PDF target → date.txt di folder foto export."
    )
    parser.add_argument("--pdf-dir", default=DEFAULT_PDF_DIR,
                        help=f"Folder PDF target. Default: {DEFAULT_PDF_DIR}")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_ROOT,
                        help=f"Folder root foto export. Default: {DEFAULT_OUTPUT_ROOT}")
    args = parser.parse_args()

    pdf_dir = Path(args.pdf_dir).resolve()
    output_root = Path(args.output_dir).resolve()

    if not pdf_dir.is_dir():
        print(f"[ERROR] Folder PDF '{pdf_dir}' tidak ditemukan.")
        return 1

    pdf_files = sorted(pdf_dir.rglob("*.pdf"))
    if not pdf_files:
        print(f"Tidak ada PDF di '{pdf_dir}'.")
        return 0

    # ── Multi-date folder management ──
    prepare_multi_date_folders(output_root, pdf_files)

    # ── Pre-scan folder lookup ──
    print(f"Pre-scan folder lookup dari '{output_root.name}'...")
    folder_lookup = build_folder_lookup(output_root)
    total_folders = sum(len(v) for v in folder_lookup.values())
    print(f"  {len(folder_lookup)} unique identifiers, {total_folders} folder.\n")

    print(f"Processing {len(pdf_files)} PDF dari '{pdf_dir.name}'...\n")

    updated = 0
    unchanged = 0
    skipped = 0
    missed = 0
    errors = 0
    fallback_used = 0

    for idx, pdf_path in enumerate(pdf_files, 1):
        fname = pdf_path.name
        if idx == 1 or idx % 25 == 0 or idx == len(pdf_files):
            print(f"[PROGRESS] {idx}/{len(pdf_files)} PDF", flush=True)

        # ── Try filename parsing first ──
        parsed = parse_target_filename(fname)
        base_category = None
        base_identifier = None
        dt = None

        if parsed:
            base_category, base_identifier, date_str = parsed
            dt = parse_date_from_filename(date_str)
        
        if not dt:
            dt = extract_date_from_pdf(pdf_path)
            fallback_used += 1
            if not dt:
                print(f"[SKIP] {fname}: tanggal tidak ditemukan", flush=True)
                skipped += 1
                continue

        formatted = format_date_target(dt)

        # Kategori multi-aset perlu semua funcloc; kategori biasa cukup dari filename.
        all_funclocs = []
        if not parsed or base_category in {"AXC", "WESEL", "SINYAL"}:
            try:
                import fitz
                with fitz.open(str(pdf_path)) as doc:
                    if len(doc) > 0:
                        text = doc[0].get_text() or ""
                        all_funclocs = extract_all_funclocs(text)
            except Exception:
                try:
                    with pdfplumber.open(str(pdf_path)) as pdf:
                        if pdf.pages:
                            text = pdf.pages[0].extract_text() or ""
                            all_funclocs = extract_all_funclocs(text)
                except Exception as exc:
                    print(f"[ERROR] {fname}: gagal membaca halaman pertama: {exc}", flush=True)
                    errors += 1

        identifiers_to_process = []
        if all_funclocs and base_category:
            for fl in all_funclocs:
                ident = extract_identifier(fl, base_category)
                if ident:
                    # Apply exceptions
                    for old, new in IDENTIFIER_EXCEPTIONS.items():
                        tokens = ident.split()
                        old_tokens = old.split()
                        if len(tokens) >= len(old_tokens) and tokens[:len(old_tokens)] == old_tokens:
                            rest = ' '.join(tokens[len(old_tokens):])
                            ident = f"{new} {rest}".strip() if rest else new
                    
                    if base_category == "CATUDAYA":
                        for prefix in ["ER SINYAL ", "ER RADIO "]:
                            if ident.startswith(prefix):
                                code = ident[len(prefix):].strip()
                                ident = f"RADIO_{code}" if prefix == "ER RADIO " else code
                                break
                    if base_category in ("PTLS", "PDSE", "PTDS"):
                        # Strip RADIO_ prefix: "RADIO_BOO" → "BOO"
                        ident = re.sub(r'^RADIO_', '', ident)
                    if base_category == "PINTU_PERLINTASAN":
                        ident = re.sub(r'\s*ELEKTRIK\s*', ' ', ident).strip()
                        ident = ident.replace(' - ', '-')
                    
                    norm = normalize_identifier(ident)
                    identifiers_to_process.append((base_category, norm, ident))

        if not identifiers_to_process and base_category and base_identifier:
            # Fallback to single identifier from filename
            norm = normalize_identifier(base_identifier)
            identifiers_to_process.append((base_category, norm, base_identifier))

        # Deduplicate preserving order
        seen = set()
        unique_idents = []
        for cat, norm, orig in identifiers_to_process:
            if orig not in seen:
                seen.add(orig)
                unique_idents.append((cat, norm, orig))

        if not unique_idents:
            print(f"[SKIP] {fname}: category/identifier tidak terdeteksi", flush=True)
            skipped += 1
            continue

        for cat, norm_id, orig_id in unique_idents:
            if cat == "PINTU_PERLINTASAN":
                cat = "JPL"
                
            # -- Look up folder --
            matches = []
            
            # Try suffixed match first (date from target PDF filename)
            if dt:
                date_suffix = dt.strftime("_%d-%m")
                suffixed_id = f"{orig_id}{date_suffix}"
                matches = folder_lookup.get((cat, suffixed_id), [])
                if not matches:
                    suffixed_norm = f"{norm_id}{date_suffix}"
                    matches = folder_lookup.get((cat, suffixed_norm), [])
            
            if not matches:
                matches = folder_lookup.get((cat, orig_id), [])
            if not matches:
                matches = folder_lookup.get((cat, norm_id), [])
            
            if not matches:
                # -- Try alternate identifiers (compound station) --
                for alt in _alternate_ids(orig_id):
                    alt_matches = folder_lookup.get((cat, alt), [])
                    if not alt_matches:
                        alt_matches = folder_lookup.get((cat, normalize_identifier(alt)), [])
                    if alt_matches:
                        matches = alt_matches
                        break

            # -- Try fallback categories (JPL↔PTPP cross-category folders) --
            if not matches:
                for alt_cat in CATEGORY_ALIASES.get(cat, []):
                    alt_matches = folder_lookup.get((alt_cat, orig_id), [])
                    if not alt_matches:
                        alt_matches = folder_lookup.get((alt_cat, norm_id), [])
                    if not alt_matches:
                        for alt in _alternate_ids(orig_id):
                            alt_matches = folder_lookup.get((alt_cat, alt), [])
                            if alt_matches:
                                break
                    if alt_matches:
                        matches = alt_matches
                        break

            if not matches:
                print(f"[MISS] {fname}: {cat}/{orig_id} -> folder tidak ditemukan", flush=True)
                missed += 1
                continue

            for folder in matches:
                date_file = folder / "date.txt"
                try:
                    if os.environ.get("OVERWRITE", "1") == "0" and date_file.exists():
                        print(f"[SKIP] {fname}: {folder.relative_to(output_root)}/date.txt sudah ada", flush=True)
                        skipped += 1
                        continue
                    if date_file.exists() and date_file.read_text(encoding="utf-8").strip() == formatted:
                        unchanged += 1
                        continue
                    date_file.write_text(formatted, encoding="utf-8")
                    updated += 1
                except Exception as e:
                    print(f"[ERROR] {fname}: {date_file}: {e}", flush=True)
                    errors += 1

    print(
        f"\nSelesai: {updated} ditulis, {unchanged} tidak berubah, "
        f"{missed} miss, {skipped} skip, {errors} error, "
        f"{fallback_used} fallback pdfplumber."
    )
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
