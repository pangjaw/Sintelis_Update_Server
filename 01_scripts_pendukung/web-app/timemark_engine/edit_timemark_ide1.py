#!/usr/bin/env python3
"""
edit_timemark_ide1.py — Versi baru: HSV Orange Isolation + Fixed-offset Stage 1c
- Hapus Stage 1, 1b, 2, 3, 4, consensus pre-scan
- Hanya: HSV isolate -> find_red_guide -> fixed offset dari guide top-right
- Fallback: get_text_box() jika tidak ada guide
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Proteksi aman protobuf untuk PaddleOCR
os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"
os.environ["OMP_WAIT_POLICY"] = "PASSIVE"
os.environ["KMP_BLOCKTIME"] = "0"
os.environ["OMP_NUM_THREADS"] = "1"

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter
import base64
import requests

import pytesseract

import openpyxl
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

# Fixed offset parameters (dari test script)
X_OFFSET_FROM_GUIDE = 6      # px right of guide right edge
Y_CENTER_OFFSET = 0          # textbox center = guide top (gy1)
BOX_HEIGHT_RATIO = 0.053     # 5.3% of image height
BOX_WIDTH_RATIO = 0.48       # 48% of image width

# Default paths
DEFAULT_INPUT = Path("03_photos_export")
DEFAULT_OUTPUT = Path("04_photos_edited")
DEFAULT_SCHEDULE = Path("schedule.json")

# ── Fallback durations (minutes) when schedule.json is not available ──
CATEGORY_DURATIONS = {
    "SINYAL": 30,
    "PERSINYALAN_ELEKTRIK": 420,
    "TELEKOMUNIKASI": 60,
    "SERAT OPTIK": 60,
    "PDSE": 420,
}
DEFAULT_DURATION = 45  # AXC, WESEL, CATU_DAYA, PINTU_PERLINTASAN, CTS, PTDS, PTLS, PTPP, JPL

MONTHS_ABBR = ["", "Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
DAYS_ID = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]


def _read_date_txt(input_dir: Path, btp: str, category: str, identifier: str) -> str | None:
    """Read date.txt from 03_photos_export for the given asset."""
    candidates = [
        DEFAULT_INPUT / btp / category / identifier / "date.txt",
        DEFAULT_INPUT.resolve() / btp / category / identifier / "date.txt",
        input_dir / "date.txt",
        input_dir / btp / category / identifier / "date.txt",
    ]
    for date_path in candidates:
        if date_path.exists():
            return date_path.read_text(encoding="utf-8").strip().removesuffix("\n")
    return None


def normalize_manual_date_text(text: str) -> str:
    """Remove a duplicated trailing HH:MM produced by the manual UI."""
    text = (text or "").strip()
    match = re.match(r"^(.*?\s\d{2}:\d{2})(?:\s+\d{2}:\d{2})+$", text)
    return match.group(1) if match else text


def _read_manual_meta(asset_dir: Path, photo_name: str) -> dict:
    """Read manual UI correction or existing coordinates for one photo from the asset folder."""
    meta_path = asset_dir / "meta.json"
    if not meta_path.exists():
        return {}
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        item = data.get(photo_name, {})
        if not item:
            return {}
        if item.get("manualEdit"):
            return item
        return {}
    except (OSError, json.JSONDecodeError):
        return {}


def parse_date_text(text: str) -> datetime | None:
    """Parse date text like 'Kamis, Jan 09 2025 [07:00]', '28 Mei 2025 [07:00]', '28-05-2025', or '2025-05-28'."""
    s = (text or "").strip()
    if not s:
        return None
    month_map = {
        "jan": 1, "januari": 1, "january": 1,
        "feb": 2, "februari": 2, "febuari": 2, "february": 2,
        "mar": 3, "maret": 3, "march": 3,
        "apr": 4, "april": 4,
        "mei": 5, "may": 5,
        "jun": 6, "juni": 6, "june": 6,
        "jul": 7, "juli": 7, "july": 7,
        "agu": 8, "agt": 8, "aug": 8, "agustus": 8, "august": 8,
        "sep": 9, "sept": 9, "september": 9,
        "okt": 10, "oct": 10, "oktober": 10, "october": 10,
        "nov": 11, "november": 11,
        "des": 12, "dec": 12, "desember": 12, "december": 12,
    }
    # 1. 'Kamis, Jan 09 2025 [07:00]'
    m = re.match(r'^\w+,\s*([A-Za-z]+)\s+(\d{1,2})\s+(\d{4})(?:\s+(\d{2}):(\d{2}))?$', s)
    if m:
        mon = month_map.get(m.group(1).lower())
        if mon:
            return datetime(int(m.group(3)), mon, int(m.group(2)),
                            int(m.group(4)) if m.group(4) else 7,
                            int(m.group(5)) if m.group(5) else 0)
    # 2. '28 Mei 2025 [07:00]' (with optional leading weekday)
    m2 = re.match(r'^(?:\w+,\s*)?(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})(?:\s+(\d{2}):(\d{2}))?$', s)
    if m2:
        mon = month_map.get(m2.group(2).lower())
        if mon:
            return datetime(int(m2.group(3)), mon, int(m2.group(1)),
                            int(m2.group(4)) if m2.group(4) else 7,
                            int(m2.group(5)) if m2.group(5) else 0)
    # 3. '28-05-2025 [07:00]' or '28/05/2025 [07:00]'
    m3 = re.match(r'^(\d{1,2})[-/](\d{1,2})[-/](\d{4})(?:\s+(\d{2}):(\d{2}))?$', s)
    if m3:
        return datetime(int(m3.group(3)), int(m3.group(2)), int(m3.group(1)),
                        int(m3.group(4)) if m3.group(4) else 7,
                        int(m3.group(5)) if m3.group(5) else 0)
    # 4. '2025-05-28 [07:00]'
    m4 = re.match(r'^(\d{4})-(\d{2})-(\d{2})(?:[T\s](\d{2}):(\d{2}))?', s)
    if m4:
        return datetime(int(m4.group(1)), int(m4.group(2)), int(m4.group(3)),
                        int(m4.group(4)) if m4.group(4) else 7,
                        int(m4.group(5)) if m4.group(5) else 0)
    return None


def format_timemark(dt: datetime, include_time: bool = True) -> str:
    if not include_time:
        return f"{DAYS_ID[dt.weekday()]}, {MONTHS_ABBR[dt.month]} {dt.day:02d} {dt.year}"
    return f"{DAYS_ID[dt.weekday()]}, {MONTHS_ABBR[dt.month]} {dt.day:02d} {dt.year} {dt.hour:02d}:{dt.minute:02d}"

# Station → BTP mapping (must match export_pdf_foto.py)
STATION_TO_BTP = {
    "BOO": "BTP JAK", "CLT": "BTP JAK",
    "BJD": "BTP JAK",
    "BNR": "BTP BD",
    "BOP": "BTP BD", "BTT": "BTP BD", "CGB": "BTP BD",
    "COS": "BTP BD", "MSG": "BTP BD", "CCR": "BTP BD",
}


# ─── HSV Orange Isolation ───
def preprocess_for_guide(img: Image.Image) -> np.ndarray:
    """Grayscale all colors EXCEPT pure red guide (Hue 0-15° or 350-360°, S>60%, V 30-80%)."""
    arr = np.array(img).astype(np.float32) / 255.0
    r, g, b = arr[:,:,0], arr[:,:,1], arr[:,:,2]

    maxc = np.maximum(np.maximum(r, g), b)
    minc = np.minimum(np.minimum(r, g), b)
    val = maxc
    delta = maxc - minc
    # Suppress divide-by-zero warning; np.where handles maxc==0 case
    with np.errstate(invalid='ignore', divide='ignore'):
        sat = np.where(maxc > 0, delta / maxc, 0)

    hue = np.zeros_like(r)
    m = delta > 0
    rm = m & (maxc == r)
    hue[rm] = (60 * ((g[rm] - b[rm]) / delta[rm])) % 360
    gm = m & (maxc == g)
    hue[gm] = 60 * ((b[gm] - r[gm]) / delta[gm]) + 120
    bm = m & (maxc == b)
    hue[bm] = 60 * ((r[bm] - g[bm]) / delta[bm]) + 240

    # Pure red mask: Hue 0-10° or 350-360°, Sat>65%, Val 25-85%
    # Excludes orange (15-35°) that appears behind red guide
    is_red = (
        ((hue <= 10) | (hue >= 350))
        & (sat >= 0.65)
        & (val >= 0.25)
        & (val <= 0.85)
    )

    gray = 0.299*r + 0.587*g + 0.114*b

    out = np.stack([
        np.where(is_red, r, gray),
        np.where(is_red, g, gray),
        np.where(is_red, b, gray),
    ], axis=2)

    return (np.clip(out, 0, 1) * 255).astype(np.uint8)


# ─── Red Guide Detection ───
def contiguous_runs(values: np.ndarray):
    idx = np.where(values)[0]
    if len(idx) == 0:
        return []
    groups = []
    s = p = int(idx[0])
    for v in idx[1:]:
        v = int(v)
        if v > p + 1:
            groups.append((s, p))
            s = v
        p = v
    groups.append((s, p))
    return groups


def find_red_guide(arr: np.ndarray, y_start: int | None = None):
    """Deteksi garis merah/kuning/oranye vertikal (Red/Yellow Guide) di area kiri foto.

    Mendukung Red, Orange, dan Yellow guide (Hue 0°-52°, Saturation >= 50%).
    Menggunakan algoritma Local Column Peak Prominence, clean vertical line check,
    dan filter lebar maksimal (<= 8-10px) tanpa Top Crop (y=0 hingga y=h).
    """
    h, w = arr.shape[:2]
    if y_start is None:
        y_start = 0

    r = arr[:,:,0].astype(float)
    g = arr[:,:,1].astype(float)
    b = arr[:,:,2].astype(float)

    # Combined Red & Yellow guide filter (r > 172)
    red_yellow = (
        (r > 172)
        & (r > g * 1.10)
        & (r > b * 1.35)
        & (g < 215)
        & (b < 160)
    )

    # HSV filter: Red, Orange, Yellow (Hue <= 52° or >= 330°) + Sat >= 63%
    delta = r - np.minimum(g, b)
    safe_delta = np.where(delta > 0, delta, 1.0)
    hue = (g - b) / safe_delta * 60
    hue = np.where(hue < 0, hue + 360, hue)
    max_c = np.maximum(np.maximum(r, g), b)
    safe_max_c = np.where(max_c > 0, max_c, 1.0)
    sat = np.where(max_c > 0, delta / safe_max_c * 100.0, 0.0)

    ry_mask = red_yellow & ((hue <= 52.0) | (hue >= 330.0)) & (sat >= 63.0)

    if y_start > 0:
        ry_mask[:y_start, :] = False
    
    # Restrict search to X <= 35% of width (max 105px)
    max_x_search = int(max(48, w * 0.35))
    ry_mask[:, max_x_search:] = False

    counts = ry_mask.astype(int).sum(axis=0)

    # Local column peak prominence + Clean vertical line check (gap check)
    prominent_mask = np.zeros(w, dtype=bool)
    min_h = max(20, int(h * 0.065))

    for x in range(max_x_search):
        if counts[x] < min_h:
            continue
        w_start = max(0, x - 6)
        w_end = min(max_x_search, x + 7)
        neighbor_vals = [counts[nx] for nx in range(w_start, w_end) if abs(nx - x) >= 3 and counts[nx] > 0]
        local_bg = np.median(neighbor_vals) if neighbor_vals else 0
        if counts[x] >= local_bg + 20 or counts[x] >= local_bg * 1.35:
            left_bg = np.min([counts[nx] for nx in range(max(0, x-4), max(0, x-1))] or [0])
            right_bg = np.min([counts[nx] for nx in range(min(max_x_search, x+2), min(max_x_search, x+5))] or [0])
            if left_bg <= counts[x] * 0.60 or right_bg <= counts[x] * 0.60:
                prominent_mask[x] = True

    max_allowed_width = 2  # Strict 1-2px guide width requirement for standard photos

    # Split wide runs at drop-off (count < peak * 0.35)
    def _split_wide_run(x1, x2, cnt_array=None):
        if cnt_array is None:
            cnt_array = counts
        run_cols = list(range(x1, x2 + 1))
        if len(run_cols) <= max_allowed_width:
            return [(x1, x2)]
        peak_count = max(cnt_array[x] for x in run_cols)
        threshold = peak_count * 0.35
        sub_runs = []
        sub_start = run_cols[0]
        for x in run_cols[1:]:
            if cnt_array[x] < threshold:
                sub_runs.append((sub_start, x - 1))
                sub_start = x
        sub_runs.append((sub_start, run_cols[-1]))
        return sub_runs

    candidates = []
    for x1, x2 in contiguous_runs(prominent_mask):
        run_width = x2 - x1 + 1
        if run_width > max_allowed_width:
            raw_sub = _split_wide_run(x1, x2)
            sub_runs = []
            for sx1, sx2 in raw_sub:
                if sx2 - sx1 + 1 <= max_allowed_width:
                    sub_runs.append((sx1, sx2))
                else:
                    # Enumerate sliding windows for sub-runs still too wide
                    for w in range(sx1, sx2 + 1):
                        sub_runs.append((w, w))
                    for w in range(sx1, sx2):
                        sub_runs.append((w, w + 1))
            if not sub_runs:
                # Fallback: enumerate all windows in original run
                for w in range(x1, x2 + 1):
                    sub_runs.append((w, w))
                for w in range(x1, x2):
                    sub_runs.append((w, w + 1))
        else:
            sub_runs = [(x1, x2)]

        for sx1, sx2 in sub_runs:
            row_has = ry_mask[:, sx1:sx2+1].sum(axis=1) > 0
            raw_runs = contiguous_runs(row_has)
            if not raw_runs:
                continue
            # Merge runs separated by small vertical gaps (<= 5 px)
            merged_runs = [list(raw_runs[0])]
            for ry1, ry2 in raw_runs[1:]:
                if ry1 - merged_runs[-1][1] <= 5:
                    merged_runs[-1][1] = ry2
                else:
                    merged_runs.append([ry1, ry2])

            for y1, y2 in merged_runs:
                guide_h = y2 - y1 + 1
                if guide_h < max(20, int(h * 0.045)):
                    continue
                score = int(ry_mask[y1:y2+1, sx1:sx2+1].sum())
                candidates.append((guide_h, score, sx1, y1, sx2, y2))

    if not candidates:
        return None
    # Sort by highest score first, then leftmost X (highest score = most pixels = true guide)
    candidates.sort(key=lambda c: (-c[1], c[2]))
    _, _, x1, y1, x2, y2 = candidates[0]
    return x1, y1, x2, y2


def find_cyan_guide_inverted(arr_orig: np.ndarray, y_start: int | None = None):
    """Deteksi red guide via invert (255 - RGB): red(200,30,30) -> cyan(55,225,225).
    
    Cyan mask formula: r_inv < 51, g_inv > 108, b_inv > 140, g_inv > r_inv * 1.40, b_inv > r_inv * 1.40.
    Menggunakan algoritma Local Column Peak Prominence (sama dengan red guide) dan NO TOP CROP.
    """
    h, w = arr_orig.shape[:2]
    if y_start is None:
        y_start = 0

    arr_inv = 255 - arr_orig.astype(np.int16)
    arr_inv = np.clip(arr_inv, 0, 255).astype(np.uint8)

    r_inv = arr_inv[:,:,0].astype(float)
    g_inv = arr_inv[:,:,1].astype(float)
    b_inv = arr_inv[:,:,2].astype(float)

    cyan_mask = (
        (r_inv < 51) & (g_inv > 108) & (b_inv > 140)
        & (g_inv > r_inv * 1.40) & (b_inv > r_inv * 1.40)
    )
    if y_start > 0:
        cyan_mask[:y_start, :] = False

    max_x_search = int(max(48, w * 0.35))
    cyan_mask[:, max_x_search:] = False

    counts = cyan_mask.astype(int).sum(axis=0)

    # ── SAME prominent check as red guide (gap check included) ──
    prominent_mask = np.zeros(w, dtype=bool)
    min_h = max(20, int(h * 0.065))

    for x in range(max_x_search):
        if counts[x] < min_h:
            continue
        w_start = max(0, x - 6)
        w_end = min(max_x_search, x + 7)
        neighbor_vals = [counts[nx] for nx in range(w_start, w_end) if abs(nx - x) >= 3 and counts[nx] > 0]
        local_bg = np.median(neighbor_vals) if neighbor_vals else 0
        if counts[x] >= local_bg + 20 or counts[x] >= local_bg * 1.35:
            left_bg = np.min([counts[nx] for nx in range(max(0, x-4), max(0, x-1))] or [0])
            right_bg = np.min([counts[nx] for nx in range(min(max_x_search, x+2), min(max_x_search, x+5))] or [0])
            if left_bg <= counts[x] * 0.60 or right_bg <= counts[x] * 0.60:
                prominent_mask[x] = True

    max_allowed_width = 2  # Strict 1-2px guide width requirement

    # Split wide runs at drop-off (count < peak * 0.35)
    def _split_wide_run(x1, x2):
        run_cols = list(range(x1, x2 + 1))
        if len(run_cols) <= max_allowed_width:
            return [(x1, x2)]
        peak_count = max(counts[x] for x in run_cols)
        threshold = peak_count * 0.35
        sub_runs = []
        sub_start = run_cols[0]
        for x in run_cols[1:]:
            if counts[x] < threshold:
                sub_runs.append((sub_start, x - 1))
                sub_start = x
        sub_runs.append((sub_start, run_cols[-1]))
        return [(sx1, sx2) for sx1, sx2 in sub_runs if sx2 - sx1 + 1 <= max_allowed_width]

    candidates = []
    for x1, x2 in contiguous_runs(prominent_mask):
        run_width = x2 - x1 + 1
        if run_width > max_allowed_width:
            sub_runs = _split_wide_run(x1, x2)
        else:
            sub_runs = [(x1, x2)]

        for sx1, sx2 in sub_runs:
            row_has = cyan_mask[:, sx1:sx2+1].sum(axis=1) > 0
            raw_runs = contiguous_runs(row_has)
            if not raw_runs:
                continue
            # Merge runs separated by small vertical gaps (<= 5 px) — same as red guide
            merged_runs = [list(raw_runs[0])]
            for ry1, ry2 in raw_runs[1:]:
                if ry1 - merged_runs[-1][1] <= 5:
                    merged_runs[-1][1] = ry2
                else:
                    merged_runs.append([ry1, ry2])

            for y1, y2 in merged_runs:
                guide_h = y2 - y1 + 1
                if guide_h < max(20, int(h * 0.045)):
                    continue
                score = int(cyan_mask[y1:y2+1, sx1:sx2+1].sum())
                candidates.append((guide_h, score, sx1, y1, sx2, y2))

    if not candidates:
        return None

    candidates.sort(key=lambda c: (c[2], -c[0], -c[1]))
    _, _, x1, y1, x2, y2 = candidates[0]
    return x1, y1, x2, y2


def find_custom1_hsv_guide(arr_orig: np.ndarray, y_start: int | None = None):
    """Custom1 HSV mask — target hue ~353° (red edge), high saturation & value.
    
    Formula: |hue - 353| ≤ 26°, sat ∈ [84,100], val ∈ [67,100].
    Uses same column peak prominence algorithm as red/cyan guides.
    """
    h, w = arr_orig.shape[:2]
    if y_start is None:
        y_start = 0

    img = Image.fromarray(arr_orig)
    hsv = img.convert('HSV')
    arr_hsv = np.array(hsv).astype(float)

    # PIL HSV is 0-255 for all channels — convert to standard ranges
    hue = (arr_hsv[:, :, 0] * 360.0 / 255.0)
    sat = (arr_hsv[:, :, 1] * 100.0 / 255.0)
    val = (arr_hsv[:, :, 2] * 100.0 / 255.0)

    # Circular hue distance from 353° (red edge)
    hue_diff = np.abs(hue - 353.0)
    hue_diff = np.where(hue_diff > 180.0, 360.0 - hue_diff, hue_diff)

    custom1_mask = (
        (hue_diff <= 26.0)
        & (sat >= 84.0) & (sat <= 100.0)
        & (val >= 67.0) & (val <= 100.0)
    )
    if y_start > 0:
        custom1_mask[:y_start, :] = False

    max_x_search = int(max(48, w * 0.35))
    custom1_mask[:, max_x_search:] = False

    counts = custom1_mask.astype(int).sum(axis=0)

    # Same prominent check as red/cyan guide
    prominent_mask = np.zeros(w, dtype=bool)
    min_h = max(20, int(h * 0.065))

    for x in range(max_x_search):
        if counts[x] < min_h:
            continue
        w_start = max(0, x - 6)
        w_end = min(max_x_search, x + 7)
        neighbor_vals = [counts[nx] for nx in range(w_start, w_end) if abs(nx - x) >= 3 and counts[nx] > 0]
        local_bg = np.median(neighbor_vals) if neighbor_vals else 0
        if counts[x] >= local_bg + 20 or counts[x] >= local_bg * 1.35:
            left_bg = np.min([counts[nx] for nx in range(max(0, x-4), max(0, x-1))] or [0])
            right_bg = np.min([counts[nx] for nx in range(min(max_x_search, x+2), min(max_x_search, x+5))] or [0])
            if left_bg <= counts[x] * 0.60 or right_bg <= counts[x] * 0.60:
                prominent_mask[x] = True

    # Custom1 detects colored AREAS (orange header), not thin lines — wider width allowed
    max_allowed_width = max(8, int(w * 0.035))

    def _split_wide_run(x1, x2):
        run_cols = list(range(x1, x2 + 1))
        if len(run_cols) <= max_allowed_width:
            return [(x1, x2)]
        peak_count = max(counts[x] for x in run_cols)
        threshold = peak_count * 0.35
        sub_runs = []
        sub_start = run_cols[0]
        for x in run_cols[1:]:
            if counts[x] < threshold:
                sub_runs.append((sub_start, x - 1))
                sub_start = x
        sub_runs.append((sub_start, run_cols[-1]))
        return [(sx1, sx2) for sx1, sx2 in sub_runs if sx2 - sx1 + 1 <= max_allowed_width]

    candidates = []
    for x1, x2 in contiguous_runs(prominent_mask):
        # Custom1 detects colored AREAS — no width limit, just group columns
        row_has = custom1_mask[:, x1:x2+1].sum(axis=1) > 0
        raw_runs = contiguous_runs(row_has)
        if not raw_runs:
            continue
        merged_runs = [list(raw_runs[0])]
        for ry1, ry2 in raw_runs[1:]:
            if ry1 - merged_runs[-1][1] <= 5:
                merged_runs[-1][1] = ry2
            else:
                merged_runs.append([ry1, ry2])

        for y1, y2 in merged_runs:
            guide_h = y2 - y1 + 1
            if guide_h < max(20, int(h * 0.045)):
                continue
            score = int(custom1_mask[y1:y2+1, x1:x2+1].sum())
            candidates.append((guide_h, score, x1, y1, x2, y2))

    if not candidates:
        return None

    candidates.sort(key=lambda c: (c[2], -c[0], -c[1]))
    _, _, x1, y1, x2, y2 = candidates[0]
    return x1, y1, x2, y2


def place_textbox_fixed_offset(guide: tuple[int,int,int,int], w: int, h: int) -> tuple[int,int,int,int]:
    """Place textbox at fixed offset from guide top-right."""
    _, gy1, gx2, _ = guide
    
    box_h = int(h * BOX_HEIGHT_RATIO)
    box_w = int(w * BOX_WIDTH_RATIO)
    
    new_x1 = gx2 + X_OFFSET_FROM_GUIDE
    new_y1 = gy1 + Y_CENTER_OFFSET - box_h // 2 + int(h * 0.018)  # shifted down
    new_x2 = min(w, new_x1 + box_w)
    new_y2 = new_y1 + box_h
    
    # Clamp
    new_y1 = max(0, new_y1)
    new_y2 = min(h, new_y2)
    new_x1 = max(0, min(new_x1, w - 1))
    new_x2 = min(w, new_x2)
    
    return new_x1, new_y1, new_x2, new_y2



def find_collage_custom_guide(arr: np.ndarray, y_start: int | None = None):
    """Deteksi guide khusus foto kolase menggunakan HSV Eyedropper mask.
    
    Formula mask:
    - hue_diff = |hue - 32.0| (dengan 360 wrap-around) <= 25.0°
    - sat in [26.0%, 86.0%]
    - val in [38.0%, 98.0%]
    """
    h, w = arr.shape[:2]
    if y_start is None:
        y_start = 0

    r = arr[:,:,0].astype(float)
    g = arr[:,:,1].astype(float)
    b = arr[:,:,2].astype(float)

    delta = r - np.minimum(g, b)
    safe_delta = np.where(delta > 0, delta, 1.0)
    max_c = np.maximum(np.maximum(r, g), b)
    safe_max_c = np.where(max_c > 0, max_c, 1.0)
    
    # Calculate Hue
    hue = np.zeros_like(r)
    mask_r = (max_c == r) & (delta > 0)
    mask_g = (max_c == g) & (delta > 0)
    mask_b = (max_c == b) & (delta > 0)
    
    hue[mask_r] = ((g[mask_r] - b[mask_r]) / safe_delta[mask_r]) % 6
    hue[mask_g] = (b[mask_g] - r[mask_g]) / safe_delta[mask_g] + 2
    hue[mask_b] = (r[mask_b] - g[mask_b]) / safe_delta[mask_b] + 4
    hue = hue * 60.0
    hue = np.where(hue < 0, hue + 360.0, hue)
    
    sat = np.where(max_c > 0, (delta / safe_max_c) * 100.0, 0.0)
    val = (max_c / 255.0) * 100.0
    
    hue_diff = np.abs(hue - 32.0)
    hue_diff = np.where(hue_diff > 180.0, 360.0 - hue_diff, hue_diff)
    
    custom_mask = (
        (hue_diff <= 25.0) &
        (sat >= 26.0) & (sat <= 86.0) &
        (val >= 38.0) & (val <= 98.0)
    )

    if y_start > 0:
        custom_mask[:y_start, :] = False

    max_x_search = int(max(48, w * 0.35))
    custom_mask[:, max_x_search:] = False

    counts = custom_mask.astype(int).sum(axis=0)

    prominent_mask = np.zeros(w, dtype=bool)
    min_h = max(20, int(h * 0.065))

    for x in range(max_x_search):
        if counts[x] < min_h:
            continue
        w_start = max(0, x - 6)
        w_end = min(max_x_search, x + 7)
        neighbor_vals = [counts[nx] for nx in range(w_start, w_end) if abs(nx - x) >= 3 and counts[nx] > 0]
        local_bg = np.median(neighbor_vals) if neighbor_vals else 0
        if counts[x] >= local_bg + 20 or counts[x] >= local_bg * 1.35:
            prominent_mask[x] = True

    max_allowed_width = max(8, int(w * 0.035))

    candidates = []
    for x1, x2 in contiguous_runs(prominent_mask):
        if x2 - x1 + 1 > max_allowed_width:
            continue
        row_has = custom_mask[:, x1:x2+1].sum(axis=1) > 0
        raw_runs = contiguous_runs(row_has)
        if not raw_runs:
            continue
        merged_runs = [list(raw_runs[0])]
        for ry1, ry2 in raw_runs[1:]:
            if ry1 - merged_runs[-1][1] <= 5:
                merged_runs[-1][1] = ry2
            else:
                merged_runs.append([ry1, ry2])

        for y1, y2 in merged_runs:
            guide_h = y2 - y1 + 1
            if guide_h < max(20, int(h * 0.045)):
                continue
            score = int(custom_mask[y1:y2+1, x1:x2+1].sum())
            candidates.append((guide_h, score, x1, y1, x2, y2))

    if not candidates:
        return None
    candidates.sort(key=lambda c: (c[2], -c[0], -c[1]))
    _, _, x1, y1, x2, y2 = candidates[0]
    return x1, y1, x2, y2


def load_cropped_collages_manifest(logs_dir: str = "logs") -> set[str]:
    """Reads logs/cropped_collages.json and returns a set of normalized relative paths."""
    manifest_file = Path(logs_dir) / "cropped_collages.json"
    if not manifest_file.exists():
        return set()
    try:
        with open(manifest_file, 'r', encoding='utf-8') as f:
            paths = json.load(f)
            return set(p.replace('\\', '/').lower() for p in paths)
    except Exception as e:
        print(f"Warning: Could not read collage manifest {manifest_file}: {e}")
        return set()


def find_old_date_by_ocr(arr: np.ndarray, w: int, h: int) -> tuple[int, int, int, int] | None:
    """Deteksi watermark tanggal putih dari PDF sumber 2026 via OCR.
    
    Format: 'Senin, Mei 25,2026:' atau 'Rabu, Nov 05 2025 07:00'
    Scan area: y > 35%, x < 70% gambar (area watermark di kiri-bawah).
    Mencoba threshold (200/180/220) untuk menangani variasi kecerahan teks.
    Returns: (x1, y1, x2, y2) atau None jika tidak ditemukan.
    """
    if os.environ.get("ENABLE_OCR_FALLBACK") == "0" or not os.path.exists(TESSERACT_PATH):
        return None

    from PIL import Image
    
    cy1 = int(h * 0.35)
    cx2 = int(w * 0.70)
    crop = arr[cy1:, :cx2]
    crop_img = Image.fromarray(crop).convert("L")
    
    # Regex: "Senin, Mei 25,2026:" atau "Senin, Nov 22 2025"
    DAY_PAT   = r"(?:Senin|Selasa|Rabu|Kamis|Jumat|Sabtu|Minggu)"
    MONTH_PAT = r"(?:Jan|Feb|Mar|Apr|Mei|Jun|Jul|Agu|Sep|Okt|Nov|Des)"
    DATE_RE   = re.compile(
        rf"({DAY_PAT})[,.]?\s*({MONTH_PAT})\s+\d{{1,2}}",
        re.IGNORECASE
    )
    
    cfg = "--psm 6 -l eng"
    all_candidates = []

    # Downscale crop jika terlalu besar (>700px) agar Tesseract 3x lebih cepat
    if crop_img.width > 700:
        factor = 700.0 / crop_img.width
        crop_img_scaled = crop_img.resize((700, int(crop_img.height * factor)), Image.Resampling.BILINEAR)
        scale_ocr = 1.0 / factor
    else:
        crop_img_scaled = crop_img
        scale_ocr = 1.0
    
    for threshold in [200, 180, 220]:
        th = crop_img_scaled.point(lambda p, t=threshold: 255 if p > t else 0)
        # Skip if almost no white pixels
        white_px = np.array(th).sum() // 255
        if white_px < 150:
            continue
        th_inv = th.point(lambda p: 255 - p)
        
        try:
            data = pytesseract.image_to_data(th_inv, config=cfg, output_type=pytesseract.Output.DICT)
        except Exception:
            continue
        
        n = len(data["text"])
        lines = {}
        for i in range(n):
            conf = int(data["conf"][i])
            if conf < 30:
                continue
            line_key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
            if line_key not in lines:
                lines[line_key] = []
            lines[line_key].append(i)
        
        threshold_found = False
        for line_key, indices in lines.items():
            line_text = " ".join(str(data["text"][i]) for i in indices if str(data["text"][i]).strip())
            m = DATE_RE.search(line_text)
            if not m:
                continue
            
            valid = [i for i in indices if str(data["text"][i]).strip()]
            if not valid:
                continue
            xs = [int(data["left"][i] * scale_ocr) for i in valid]
            ys = [int(data["top"][i] * scale_ocr) for i in valid]
            ws = [int(data["width"][i] * scale_ocr) for i in valid]
            hs = [int(data["height"][i] * scale_ocr) for i in valid]
            confs = [int(data["conf"][i]) for i in valid]
            avg_conf = sum(confs) / len(confs)
            
            x1 = min(xs)
            y1 = min(ys) + cy1
            x2 = max(x + wi for x, wi in zip(xs, ws))
            y2 = max(y + hi for y, hi in zip(ys, hs)) + cy1
            
            all_candidates.append((avg_conf, x1, y1, x2, y2))
            if avg_conf >= 55:
                threshold_found = True
        
        if threshold_found:
            break
    
    if not all_candidates:
        return None
    
    # Pilih candidate dengan confidence tertinggi
    all_candidates.sort(key=lambda c: c[0], reverse=True)
    best_conf, x1, y1, x2, y2 = all_candidates[0]
    
    # Perluas box sedikit untuk textbox watermark baru
    box_h = y2 - y1
    pad_y = max(1, int(box_h * 0.3))
    return (x1, y1 - pad_y, x2, y2 + pad_y)


def get_text_box(w: int, h: int) -> tuple[int, int, int, int]:
    """Fallback area when no guide detected (bottom-left watermark position)."""
    x1 = int(w * 0.047)
    y1 = int(h * 0.735)
    x2 = int(w * 0.49)
    y2 = int(h * 0.82)
    return x1, y1, x2, y2


# ─── Diffuse Fill (inpainting) ───
def diffuse_fill(arr: np.ndarray, mask: np.ndarray, steps: int = 20) -> np.ndarray:
    filled = arr.copy().astype(np.float32)
    mask3 = mask[:, :, None]
    for _ in range(steps):
        up = np.vstack([filled[:1], filled[:-1]])
        down = np.vstack([filled[1:], filled[-1:]])
        left = np.hstack([filled[:, :1], filled[:, :-1]])
        right = np.hstack([filled[:, 1:], filled[:, -1:]])
        avg = (up + down + left + right) * 0.25
        filled = np.where(mask3, avg, filled)
    return np.clip(filled, 0, 255).astype(np.uint8)


# ─── Local AI Inpainting (LaMa Neural Network) ───
_LAMA_SESSION = None

def _setup_cuda_dlls():
    """Register pip-installed NVIDIA CUDA/cuDNN/cuFFT DLL paths into Windows search path."""
    if sys.platform != "win32":
        return
    try:
        import site
        dirs_to_check = []
        base_sites = list(site.getsitepackages())
        user_site = getattr(site, "getusersitepackages", lambda: "")()
        if user_site:
            base_sites.append(user_site)

        for sp in base_sites:
            nvidia_dir = os.path.join(sp, "nvidia")
            if os.path.isdir(nvidia_dir):
                for entry in os.listdir(nvidia_dir):
                    bin_dir = os.path.join(nvidia_dir, entry, "bin")
                    if os.path.isdir(bin_dir):
                        dirs_to_check.append(bin_dir)

        for p in dirs_to_check:
            if os.path.isdir(p):
                try:
                    os.add_dll_directory(p)
                except Exception:
                    pass
                if p not in os.environ.get("PATH", ""):
                    os.environ["PATH"] = p + os.pathsep + os.environ.get("PATH", "")
    except Exception:
        pass


def get_lama_session():
    global _LAMA_SESSION
    if _LAMA_SESSION is None:
        try:
            _setup_cuda_dlls()
            import onnxruntime as ort
            import shutil

            # 1. Cek SSD Cache C: (%LOCALAPPDATA%/Sintelis/models/lama_fp32.onnx) untuk pembacaan super cepat
            local_appdata = os.environ.get("LOCALAPPDATA")
            ssd_model = os.path.join(local_appdata, "Sintelis", "models", "lama_fp32.onnx") if local_appdata else None
            model_path = None
            if ssd_model and os.path.isfile(ssd_model):
                model_path = ssd_model
            else:
                src_model = os.path.join(os.path.dirname(__file__), "models", "lama_fp32.onnx")
                if not os.path.isfile(src_model):
                    src_model = os.path.join(os.path.dirname(__file__), "models", "lama_int8.onnx")
                if os.path.isfile(src_model):
                    if ssd_model:
                        try:
                            os.makedirs(os.path.dirname(ssd_model), exist_ok=True)
                            shutil.copy2(src_model, ssd_model)
                            model_path = ssd_model
                        except Exception:
                            model_path = src_model
                    else:
                        model_path = src_model

            if model_path and os.path.isfile(model_path):
                opts = ort.SessionOptions()
                opts.intra_op_num_threads = 4
                opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

                avail = ort.get_available_providers()
                preferred_providers = []
                if 'CUDAExecutionProvider' in avail:
                    preferred_providers.append('CUDAExecutionProvider')
                preferred_providers.append('CPUExecutionProvider')

                _LAMA_SESSION = ort.InferenceSession(model_path, sess_options=opts, providers=preferred_providers)
                print(f"[LaMa AI Init] Loaded model from {'SSD (C:)' if 'AppData' in model_path else 'Disk D:'}: {os.path.basename(model_path)} | Providers: {_LAMA_SESSION.get_providers()}", flush=True)
            else:
                _LAMA_SESSION = False
        except Exception as e:
            print(f"[LaMa AI Init Failed] Error: {e}", flush=True)
            _LAMA_SESSION = False
    return _LAMA_SESSION if _LAMA_SESSION else None


def lama_inpaint(img_arr: np.ndarray, box: tuple[int, int, int, int]) -> np.ndarray:
    """Inpaint box region using local AI LaMa neural network for photorealistic texture synthesis."""
    sess = get_lama_session()
    if not sess:
        return None
    try:
        import cv2
        h, w = img_arr.shape[:2]
        x1, y1, x2, y2 = box
        if y2 <= y1 or x2 <= x1:
            return None
        # Padding adaptif (3-4px) untuk memastikan seluruh tepi glif teks lama ter-mask secara utuh
        pad_y = max(3, int(h * 0.012))
        pad_x = max(3, int(w * 0.012))
        my1 = max(0, y1 - pad_y)
        my2 = min(h, y2 + pad_y)
        mx1 = max(0, x1 - pad_x)
        mx2 = min(w, x2 + pad_x)

        mask = np.zeros((h, w), dtype=np.uint8)
        mask[my1:my2, mx1:mx2] = 255

        img_resized = cv2.resize(img_arr, (512, 512), interpolation=cv2.INTER_AREA)
        mask_resized = cv2.resize(mask, (512, 512), interpolation=cv2.INTER_NEAREST)

        img_t = (img_resized.astype(np.float32) / 255.0).transpose(2, 0, 1)[None, ...]
        mask_t = (mask_resized > 127).astype(np.float32)[None, None, ...]

        outputs = sess.run(None, {'image': img_t, 'mask': mask_t})
        out = outputs[0][0].transpose(1, 2, 0)
        out = np.clip(out, 0, 255).astype(np.uint8)
        out_orig_size = cv2.resize(out, (w, h), interpolation=cv2.INTER_CUBIC)

        blended = img_arr.copy()
        mask_bool = mask > 0
        blended[mask_bool] = out_orig_size[mask_bool]
        return blended
    except Exception as e:
        print(f"[LaMa Inpaint Error] {e}", flush=True)
        return None


# ─── Font ───
# Cache font at module level to avoid repeated disk reads
_FONT_CACHE = {}

def get_font(size: int):
    if size in _FONT_CACHE:
        return _FONT_CACHE[size]
    fonts_dir = Path(__file__).resolve().parent / "fonts"
    candidates = [
        fonts_dir / "Roboto-Bold.ttf",                                              # Font Asli Kamera Timemark Android
        fonts_dir / "Roboto-Medium.ttf",
        fonts_dir / "Roboto-Regular.ttf",
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "arialbd.ttf",   # Fallback Windows
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "segoeuib.ttf",  # Segoe UI Bold
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "calibrib.ttf",  # Calibri Bold
        "DejaVuSans-Bold.ttf",
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "arial.ttf",
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "segoeui.ttf",
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "calibri.ttf",
        "DejaVuSans.ttf",
    ]
    for fp in candidates:
        if isinstance(fp, str):
            try:
                font = ImageFont.truetype(fp, size=size)
                _FONT_CACHE[size] = font
                return font
            except:
                continue
        if fp.exists():
            font = ImageFont.truetype(str(fp), size=size)
            _FONT_CACHE[size] = font
            return font
    return ImageFont.load_default()
def draw_textbox(img: Image.Image, box: tuple[int,int,int,int], text: str, no_bg: bool = False) -> Image.Image:
    x1, y1, x2, y2 = box
    w, h = img.size
    box_h = y2 - y1
    font_size = max(9, min(160, int(w * 0.038)))
    font = get_font(font_size)

    dummy = ImageDraw.Draw(Image.new("L", (1,1)))
    fit_stroke = 1 if font_size >= 28 else 0
    bbox = dummy.textbbox((0,0), text, font=font, stroke_width=fit_stroke)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    pad_x = 0 if no_bg else max(6, int(w * 0.012))
    pad_y = max(2, int(h * 0.005))
    fit_w = tw + (2 * pad_x)

    sx1 = max(0, x1)
    sy1 = max(0, y1)
    target_w = max(fit_w, x2 - x1) if (x2 > x1 and (x2 - x1) <= int(w * 0.40)) else fit_w
    sx2 = min(w, sx1 + target_w)
    sy2 = min(h, y2)
    shape_box = (sx1, sy1, sx2, sy2)

    tx = sx1 + pad_x
    ty = sy1 + ((box_h - th) // 2) - bbox[1]

    out = img.copy()

    # Efek Buram / Frosted Glass Gaussian Blur & Pill Hitam di belakang box (hanya jika no_bg=False)
    if not no_bg:
        bw = sx2 - sx1
        bh = sy2 - sy1
        if bw > 0 and bh > 0:
            radius = max(2, int(box_h * 0.25))
            blur_radius = max(3, int(box_h * 0.16))
            crop_box = out.crop(shape_box)
            blurred_box = crop_box.filter(ImageFilter.GaussianBlur(radius=blur_radius))
            mask = Image.new("L", (bw, bh), 0)
            mdraw = ImageDraw.Draw(mask)
            mdraw.rounded_rectangle((0, 0, bw, bh), radius=radius, fill=255)
            out.paste(blurred_box, (sx1, sy1), mask)

            overlay = Image.new("RGBA", out.size, (0, 0, 0, 0))
            odraw = ImageDraw.Draw(overlay)
            odraw.rounded_rectangle(shape_box, radius=radius, fill=(0, 0, 0, 140))
            out = Image.alpha_composite(out.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(out)
    so = max(1, int(font_size * 0.025))
    draw.text((tx+so, ty+so), text, font=font, fill=(35,35,35), stroke_width=fit_stroke, stroke_fill=(35,35,35))
    draw.text((tx, ty), text, font=font, fill=(248,248,248))
    return out


# (duplicate defs removed - see live versions below)


# ─── Main ───
def sanitize_segment(text: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', '_', text).strip()


def asset_output_dir(root: Path, btp: str, category: str, identifier: str) -> Path:
    return root / sanitize_segment(btp) / category / sanitize_segment(identifier)


def _folder_key_from_path(rel: Path, input_dir: Path | None = None) -> tuple[str, str, str] | None:
    """Extract (btp, category, identifier) from relative path for flat structure.

    Structure: [BTP/]category/identifier/photo.jpg
    Returns: (btp, category, identifier) or None
    """
    parts = rel.parts
    btp_shift = 1 if parts and parts[0].startswith("BTP") else 0
    if len(parts) >= 3 + btp_shift:
        btp = parts[0] if btp_shift else "BTP JAK"
        return btp, parts[0 + btp_shift], parts[1 + btp_shift]
    return None






def locate_date_box(arr_orig: np.ndarray, w: int, h: int,
                    y_override: int | None = None, consensus_gy1: int | None = None,
                    is_collage: bool = False):
    """
    Multi-stage detection (Full Height / NO TOP CROP).
    Custom Collage guide -> Red/Yellow guide -> Cyan guide -> Folder consensus -> OCR -> fixed position.
    Returns: (box, stage_name)
    """
    if y_override is not None:
        box_h = int(h * BOX_HEIGHT_RATIO)
        y1 = max(0, y_override - box_h // 2)
        y2 = min(h, y1 + box_h)
        x1 = int(w * 0.047)
        x2 = int(w * 0.49)
        return (x1, y1, x2, y2), "stage_0_override"

    # If photo is a cropped collage, try custom collage HSV guide first
    if is_collage:
        c_guide = find_collage_custom_guide(arr_orig, y_start=0)
        if c_guide is not None:
            box = place_textbox_fixed_offset(c_guide, w, h)
            return box, "stage_1c_guide_original"

    # Stage 1: Red/Yellow guide (NO TOP CROP, scans y=0..h)
    guide = find_red_guide(arr_orig, y_start=0)
    if guide is not None:
        box = place_textbox_fixed_offset(guide, w, h)
        return box, "stage_1c_guide_original"

    # Bottom zone for fallback stages (Stage 2..5)
    y_bot = int(h * 0.54)
    zone_arr = arr_orig[y_bot:, :]

    # Stage 2: Cyan inverted guide
    guide = find_cyan_guide_inverted(zone_arr, y_start=0)
    if guide is not None:
        guide = (guide[0], y_bot + guide[1], guide[2], y_bot + guide[3])
        box = place_textbox_fixed_offset(guide, w, h)
        return box, "stage_2_invert_guide"

    # Stage 3: Custom1 HSV guide (red edge ~353°)
    guide = find_custom1_hsv_guide(zone_arr, y_start=0)
    if guide is not None:
        guide = (guide[0], y_bot + guide[1], guide[2], y_bot + guide[3])
        box = place_textbox_fixed_offset(guide, w, h)
        return box, "stage_3_custom1_hsv"

    # Stage 4: Folder consensus
    if consensus_gy1 is not None:
        actual_gy = consensus_gy1 if consensus_gy1 >= y_bot else (y_bot + consensus_gy1)
        synthetic = (8, actual_gy, 9, actual_gy + 84)
        box = place_textbox_fixed_offset(synthetic, w, h)
        return box, "stage_1c_guide_consensus"

    # Stage 5: OCR old date
    ocr_box = find_old_date_by_ocr(zone_arr, w, h)
    if ocr_box is not None:
        return ocr_box, "stage_ocr_old_date"

    # Fallback
    fallback = get_text_box(w, h)
    return fallback, "stage_fallback"


# ─── Schedule Support ───
def load_schedule(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def iso_to_timemark(iso_str: str, include_time: bool = True) -> str:
    """2026-07-11T09:30:00 -> Rabu, Jul 11 2026 09:30"""
    dt = datetime.fromisoformat(iso_str)
    days = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
    months = ["", "Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
    if not include_time:
        return f"{days[dt.weekday()]}, {months[dt.month]} {dt.day:02d} {dt.year}"
    return f"{days[dt.weekday()]}, {months[dt.month]} {dt.day:02d} {dt.year} {dt.hour:02d}:{dt.minute:02d}"


def normalize_schedule_identifier(identifier: str) -> str:
    """Map legacy 2025 identifier to current 2026 photo folder."""
    return "ZP 41 BOO" if identifier.strip().upper() == "ZP 41B BOO" else identifier


def _strip_date_suffix(ident: str) -> str:
    return re.sub(r'_\d{2}-\d{2}(?:-\d{4})?(?:_part\d+)?$', '', ident.strip())


def build_schedule_lookup(schedule_data: dict, tim_filter: int | None = None, include_time: bool = True):
    """Build {(btp, category, identifier, photo): (timemark_text, tim_n)}.
    Also indexes base_identifier (without _DD-MM suffix) so 2026 photo folders (e.g. MJ20 CLT_22-05)
    match 2025 schedule entries (e.g. MJ20 CLT_13-05).
    """
    lookup = {}
    for sched in schedule_data.get("schedules", []):
        tim_n = sched.get("tim", 1)
        if tim_filter is not None and tim_n != tim_filter:
            continue
        btp = sched.get("btp", "BTP JAK")
        category = sched.get("category", "UNKNOWN")
        identifier = normalize_schedule_identifier(sched.get("identifier") or sched.get("pdf_stem", ""))
        base_id = _strip_date_suffix(identifier)
        for pname, iso_ts in sched.get("photos", {}).items():
            new_val = (iso_to_timemark(iso_ts, include_time=include_time), tim_n)
            key = (btp, category, identifier, pname)
            existing = lookup.get(key)
            if existing is None or tim_n > existing[1]:
                lookup[key] = new_val
            if base_id and base_id != identifier:
                base_key = (btp, category, base_id, pname)
                if base_key not in lookup:
                    lookup[base_key] = new_val
    return lookup




def find_guide_by_mask_direct(arr_orig: np.ndarray, mask_type: str = "red"):
    """Pixel Inspector Direct Mask Guide Finder (No strict bounding box / flank rules)."""
    h, w = arr_orig.shape[:2]
    max_x = int(w * 0.35)

    if mask_type == "cyan":
        arr_inv = np.clip(255 - arr_orig.astype(np.int16), 0, 255).astype(np.uint8)
        r = arr_inv[:, :, 0].astype(float)
        g = arr_inv[:, :, 1].astype(float)
        b = arr_inv[:, :, 2].astype(float)
        mask = (r < 65) & (g > 90) & (b > 120) & (g > r * 1.3) & (b > r * 1.3)
    elif mask_type == "custom":
        r = arr_orig[:, :, 0].astype(float)
        g = arr_orig[:, :, 1].astype(float)
        b = arr_orig[:, :, 2].astype(float)
        mask = (r > 120) & (r > g * 1.3) & (r > b * 1.3) & (g < 210) & (b < 180)
    else:  # red mask
        r = arr_orig[:, :, 0].astype(float)
        g = arr_orig[:, :, 1].astype(float)
        b = arr_orig[:, :, 2].astype(float)
        mask = (r > 140) & (r > g * 1.4) & (r > b * 1.4) & (g < 195) & (b < 165)

    mask[:, max_x:] = False

    counts = mask.astype(int).sum(axis=0)
    if counts.max() < 10:
        return None

    best_x = int(np.argmax(counts))
    col_mask = mask[:, max(0, best_x - 1):min(w, best_x + 2)].any(axis=1)
    y_indices = np.where(col_mask)[0]
    if len(y_indices) < 10:
        return None

    y1, y2 = int(y_indices[0]), int(y_indices[-1])
    return (best_x, y1, best_x, y2)


def _detect_guideline_for_label(arr: np.ndarray, w: int, h: int, is_collage: bool = False):
    """Return the actual pixel guideline used for YOLO capture, if present."""
    if is_collage:
        guide = find_collage_custom_guide(arr, y_start=0)
        if guide is not None:
            return tuple(map(int, guide))
    guide = find_red_guide(arr, y_start=0)
    if guide is not None:
        return tuple(map(int, guide))
    y_bot = int(h * 0.54)
    guide = find_cyan_guide_inverted(arr[y_bot:, :], y_start=0)
    if guide is not None:
        return int(guide[0]), y_bot + int(guide[1]), int(guide[2]), y_bot + int(guide[3])
    guide = find_custom1_hsv_guide(arr[y_bot:, :], y_start=0)
    if guide is not None:
        return int(guide[0]), y_bot + int(guide[1]), int(guide[2]), y_bot + int(guide[3])
    return None


def _write_yolo_label(image_path: Path, image_size: tuple[int, int], guide):
    """Write one class-0 YOLO label beside the source image."""
    label_path = image_path.with_suffix(".txt")
    if guide is None:
        return
    width, height = image_size
    if width <= 0 or height <= 0:
        return
    x1, y1, x2, y2 = guide
    x1 = max(0, min(int(x1), width))
    y1 = max(0, min(int(y1), height))
    x2 = max(x1, min(int(x2), width))
    y2 = max(y1, min(int(y2), height))
    if x2 <= x1 or y2 <= y1:
        return
    label = f"0 {(x1 + x2) / 2 / width:.6f} {(y1 + y2) / 2 / height:.6f} {(x2 - x1) / width:.6f} {(y2 - y1) / height:.6f}\n"
    try:
        label_path.write_text(label, encoding="utf-8")
    except Exception:
        pass


def _read_yolo_label(image_path: Path, w: int, h: int) -> tuple[int, int, int, int] | None:
    """Read coordinate from beside the source image (0.txt, 50.txt, 100.txt).
    Supports both:
    - Narrow vertical guide YOLO box (bw < 0.08) -> converted via place_textbox_fixed_offset()
    - Full textbox YOLO box (bw >= 0.08) -> used directly as (x1, y1, x2, y2)
    """
    label_path = image_path.with_suffix(".txt")
    if not label_path.is_file():
        return None
    try:
        raw = label_path.read_text(encoding="utf-8", errors="ignore").strip()
        if not raw:
            return None
        first_line = raw.splitlines()[0].strip()
        parts = first_line.split()
        if len(parts) >= 5:
            xc = float(parts[1])
            yc = float(parts[2])
            bw = float(parts[3])
            bh = float(parts[4])
            if 0.0 <= xc <= 1.0 and 0.0 <= yc <= 1.0 and 0.0 < bw <= 1.0 and 0.0 < bh <= 1.0:
                x1 = max(0, min(w - 1, int(round((xc - bw / 2.0) * w))))
                y1 = max(0, min(h - 1, int(round((yc - bh / 2.0) * h))))
                x2 = max(x1 + 1, min(w, int(round((xc + bw / 2.0) * w))))
                y2 = max(y1 + 1, min(h, int(round((yc + bh / 2.0) * h))))
                # Jika lebar < 8% gambar, berarti label berisi garis vertikal guide (gx1, gy1, gx2, gy2)
                if bw < 0.08:
                    return place_textbox_fixed_offset((x1, y1, x2, y2), w, h)
                # Jika lebar >= 8%, berarti label berisi bounding box textbox langsung
                box_h = max(16, int(h * BOX_HEIGHT_RATIO))
                return (x1, y1, x2, min(h, y1 + box_h))
    except Exception:
        return None
    return None


# ─── Google Cloud Vision Integration ───
def _get_gv_cache_file() -> Path:
    candidates = [
        Path("logs/google_vision_cache.json"),
        Path(__file__).resolve().parent.parent / "logs" / "google_vision_cache.json",
        Path(__file__).resolve().parents[2] / "logs" / "google_vision_cache.json",
    ]
    for c in candidates:
        if c.exists():
            return c
    d = Path(__file__).resolve().parent.parent / "logs"
    if d.exists() or Path(__file__).resolve().parent.parent.exists():
        return d / "google_vision_cache.json"
    return Path("logs/google_vision_cache.json")

_GV_CACHE = {}

def load_google_vision_cache():
    global _GV_CACHE
    c_file = _get_gv_cache_file()
    if c_file.exists():
        try:
            with open(c_file, "r", encoding="utf-8") as f:
                _GV_CACHE = json.load(f)
        except Exception:
            _GV_CACHE = {}

def save_google_vision_cache():
    c_file = _get_gv_cache_file()
    c_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(c_file, "w", encoding="utf-8") as f:
            json.dump(_GV_CACHE, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

def get_google_vision_api_key():
    candidates = [
        Path("config/google_vision_api_key.txt"),
        Path(__file__).resolve().parent.parent / "config" / "google_vision_api_key.txt",
        Path(__file__).resolve().parents[2] / "config" / "google_vision_api_key.txt",
        Path("experiments_google_vision/api_key.txt"),
    ]
    for p in candidates:
        if p.exists():
            k = p.read_text(encoding="utf-8").strip()
            if k:
                return k
    return os.environ.get("GOOGLE_VISION_API_KEY") or os.environ.get("GOOGLE_API_KEY")

def detect_timemark_via_google_vision(image_path: Path, w: int, h: int, arr_orig: np.ndarray | None = None, is_collage: bool = False) -> tuple[tuple[int, int, int, int] | None, str]:
    """Detect timemark box using Google Cloud Vision REST API.
    Returns: ((x1, y1, x2, y2), stage_name) or (None, reason)
    """
    global _GV_CACHE
    if not _GV_CACHE:
        load_google_vision_cache()

    rel_key = str(image_path).replace("\\", "/")
    if "03_photos_cropped_temp" in rel_key and Path(image_path).is_file():
        rel_key = f"{rel_key}@{int(Path(image_path).stat().st_mtime)}"

    short_key = None
    for kw in ["03_export_foto", "03_photos_export", "04_photos_edited", "04_edit_foto"]:
        if kw in rel_key:
            short_key = rel_key.split(kw)[-1].strip("/")
            break

    for k in [rel_key, short_key]:
        if k and k in _GV_CACHE:
            cached_box = _GV_CACHE[k]
            # Only use cache if it was not an anomalous narrow/offset box
            if cached_box and len(cached_box) == 4 and cached_box[0] <= 25 and (cached_box[2] - cached_box[0]) >= 50:
                return tuple(cached_box), "stage_google_vision"

    api_key = get_google_vision_api_key()
    if not api_key:
        return None, "no_api_key"

    url = f"https://vision.googleapis.com/v1/images:annotate?key={api_key}"
    
    # Downscale image to max 1280px to reduce payload by 98% (faster upload over SMB/internet)
    scale_x = 1.0
    scale_y = 1.0
    try:
        max_dim = 1280
        if w > max_dim or h > max_dim:
            if w >= h:
                down_w = max_dim
                down_h = max(1, int(round(h * (max_dim / float(w)))))
            else:
                down_h = max_dim
                down_w = max(1, int(round(w * (max_dim / float(h)))))
            scale_x = w / float(down_w)
            scale_y = h / float(down_h)

            if arr_orig is not None:
                pil_to_send = Image.fromarray(arr_orig).resize((down_w, down_h), Image.Resampling.BILINEAR)
            else:
                pil_to_send = Image.open(image_path).convert("RGB").resize((down_w, down_h), Image.Resampling.BILINEAR)

            buf = io.BytesIO()
            pil_to_send.save(buf, format="JPEG", quality=82)
            img_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        else:
            with open(image_path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        return None, f"file_read_error_{e}"

    payload = {
        "requests": [
            {
                "image": {"content": img_b64},
                "features": [{"type": "TEXT_DETECTION"}]
            }
        ]
    }

    try:
        resp = requests.post(url, json=payload, timeout=20)
        if resp.status_code in (401, 403, 429):
            err_text = resp.text
            if "BILLING_DISABLED" in err_text or "billing" in err_text.lower() or resp.status_code == 429 or "RESOURCE_EXHAUSTED" in err_text:
                return None, "quota_exceeded"
            return None, f"auth_error_{resp.status_code}"
        if resp.status_code != 200:
            return None, f"http_error_{resp.status_code}"

        data = resp.json()
        responses = data.get("responses", [{}])[0]
        if "error" in responses:
            err_msg = responses["error"].get("message", "")
            if "BILLING_DISABLED" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                return None, "quota_exceeded"
            return None, "api_error"

        text_annotations = responses.get("textAnnotations", [])
        if len(text_annotations) <= 1:
            return None, "no_text_detected"

        word_annotations = text_annotations[1:]
        date_keywords = [
            "2024", "2025", "2026",
            "jan", "feb", "mar", "apr", "mei", "may", "jun", "jul", "agt", "agu", "aug", "sep", "okt", "oct", "nov", "des", "dec",
            "january", "february", "march", "april", "june", "july", "august", "september", "october", "november", "december",
            "sen", "sel", "rab", "kam", "jum", "sab", "min",
            "senin", "selasa", "rabu", "kamis", "jumat", "sabtu", "minggu",
            "mon", "tue", "wed", "thu", "fri", "sat", "sun",
            "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
            "pagi", "siang", "sore", "malam", "wib", "am", "pm"
        ]
        typo_patterns = [
            re.compile(r'm[iaou]ng*u*', re.I),
            re.compile(r's[au]bt*u*', re.I),
            re.compile(r's[au]lc[au]n*', re.I),
            re.compile(r's[ea]n[ie]n*', re.I),
            re.compile(r's[ea]l[ae]s*a*', re.I),
            re.compile(r'r[ab]b*u*', re.I),
            re.compile(r'k[ae]m[ie]s*', re.I),
            re.compile(r'j[ua]m.*', re.I),
            re.compile(r'sat.*', re.I),
            re.compile(r'sun.*', re.I),
        ]

        all_words = []
        date_words = []
        for ann in word_annotations:
            txt = ann.get("description", "")
            norm_verts = ann.get("boundingPoly", {}).get("normalizedVertices", [])
            verts = ann.get("boundingPoly", {}).get("vertices", [])
            if norm_verts and any(v.get("x") is not None for v in norm_verts):
                xs = [int(round(v.get("x", 0.0) * w)) for v in norm_verts]
                ys = [int(round(v.get("y", 0.0) * h)) for v in norm_verts]
            elif verts:
                xs = [int(round(v.get("x", 0) * scale_x)) for v in verts]
                ys = [int(round(v.get("y", 0) * scale_y)) for v in verts]
            else:
                continue
            x1, y1, x2, y2 = min(xs), min(ys), max(xs), max(ys)
            cy = (y1 + y2) // 2
            word_obj = {"text": txt, "bbox": [x1, y1, x2, y2], "cy": cy}
            all_words.append(word_obj)

            is_date = (
                any(k in txt.lower() for k in date_keywords) or
                any(p.match(txt) for p in typo_patterns) or
                (any(c.isdigit() for c in txt) and (":" in txt or "-" in txt or "/" in txt))
            )
            # Must be in left/watermark zone (x < 60% of width)
            if is_date and x1 < int(w * 0.60):
                date_words.append(word_obj)

        if not date_words:
            return None, "no_date_words"

        # Anchor finding: year (2024/2025/2026) or month
        anchor = None
        for dw in date_words:
            t = dw["text"].lower()
            if any(y in t for y in ["2024", "2025", "2026"]):
                anchor = dw
                break
        if not anchor:
            for dw in date_words:
                t = dw["text"].lower()
                if any(m in t for m in ["jan", "feb", "mar", "apr", "mei", "may", "jun", "jul", "agu", "aug", "sep", "okt", "oct", "nov", "des", "dec"]):
                    anchor = dw
                    break
        if not anchor:
            anchor = date_words[0]

        anchor_cy = anchor["cy"]
        # Spatial line sweep: include ALL words on the same horizontal line in watermark zone
        same_line = []
        for wobj in all_words:
            if abs(wobj["cy"] - anchor_cy) <= 8 and wobj["bbox"][0] < int(w * 0.60) and wobj["text"].lower() not in ["timemark", "camera", "gps"]:
                same_line.append(wobj["bbox"])

        if not same_line:
            same_line = [anchor["bbox"]]

        min_x = min(b[0] for b in same_line)
        min_y = min(b[1] for b in same_line)
        max_x = max(b[2] for b in same_line)
        max_y = max(b[3] for b in same_line)

        # Smart Guide Alignment: check if guide exists and aligns with top endpoint gy1
        found_guide = None
        if arr_orig is not None:
            if is_collage:
                found_guide = find_collage_custom_guide(arr_orig, y_start=0)
            if found_guide is None:
                found_guide = find_red_guide(arr_orig, y_start=0)
            if found_guide is None:
                y_bot = int(h * 0.54)
                found_guide = find_cyan_guide_inverted(arr_orig[y_bot:, :], y_start=0) or find_custom1_hsv_guide(arr_orig[y_bot:, :], y_start=0)
                if found_guide:
                    found_guide = (found_guide[0], y_bot + found_guide[1], found_guide[2], y_bot + found_guide[3])

        if found_guide:
            gx1, gy1, gx2, gy2 = found_guide
            y_center = (min_y + max_y) // 2
            # Beside guide: expand left boundary if Vision missed leftmost word
            if abs(y_center - gy1) <= int(h * 0.15) or y_center >= gy1 - 10:
                if min_x > gx2 + 10:
                    min_x = gx2 + 6
            elif y_center < gy1 - 10:
                # Text above guide
                min_x = min(min_x, gx1)

        box_h = max(16, int(h * BOX_HEIGHT_RATIO))
        old_w = (max_x - min_x) + 6
        y_center = (min_y + max_y) // 2
        y1 = max(0, y_center - box_h // 2)
        y2 = min(h, y1 + box_h)
        x1 = max(0, min_x - 3)
        x2 = min(w, x1 + old_w)
        box = (x1, y1, x2, y2)

        _GV_CACHE[rel_key] = list(box)
        if short_key:
            _GV_CACHE[short_key] = list(box)
        save_google_vision_cache()
        return box, "stage_google_vision"

    except Exception as e:
        return None, f"exception_{e}"


# Global detector tracker for pause/resume fallback

# ponytail: PaddleOCR worker bridge calling Python 3.11
PADDLE_PY = r"C:\Users\dikarm\AppData\Local\Programs\Python\Python311\python.exe"
PADDLE_WORKER = str(Path(__file__).parent / "paddle_worker.py")
_PADDLE_CACHE = {}
_IN_PROCESS_OCR_FN = None

def register_in_process_ocr(fn):
    global _IN_PROCESS_OCR_FN
    _IN_PROCESS_OCR_FN = fn

def detect_timemark_via_paddle_ocr(image_path: Path, w: int, h: int) -> tuple[tuple[int, int, int, int] | None, str]:
    global _PADDLE_CACHE, _IN_PROCESS_OCR_FN
    k = str(image_path)
    if k in _PADDLE_CACHE:
        return _PADDLE_CACHE[k]

    # Jalur Ultra Cepat 1 (Direct In-Memory ~0.14s): Jika dipanggil langsung di dalam resident service
    if _IN_PROCESS_OCR_FN is not None:
        try:
            res = _IN_PROCESS_OCR_FN(str(image_path))
            if res.get("ok") and res.get("box"):
                box = tuple(res["box"])
                _PADDLE_CACHE[k] = (box, "stage_paddle_ocr")
                return box, "stage_paddle_ocr"
            else:
                _PADDLE_CACHE[k] = (None, "stage_fallback")
                return None, "stage_fallback"
        except Exception:
            _PADDLE_CACHE[k] = (None, "stage_fallback")
            return None, "stage_fallback"

    # Jalur Cepat 2 (HTTP Daemon ~0.14s): Cek apakah resident daemon sedang aktif di background
    try:
        import urllib.request
        req = urllib.request.Request(
            "http://127.0.0.1:58253/ocr",
            data=json.dumps({"image_path": str(image_path), "w": w, "h": h}).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=4.0) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("ok") and data.get("box"):
                    box = tuple(data["box"])
                    _PADDLE_CACHE[k] = (box, "stage_paddle_ocr")
                    return box, "stage_paddle_ocr"
    except Exception:
        pass

    # Fallback jika daemon belum menyala: Jalankan subproses mandiri
    if not os.path.exists(PADDLE_PY) or not os.path.exists(PADDLE_WORKER):
        return None, "stage_paddle_not_found"
    try:
        proc = subprocess.run([PADDLE_PY, PADDLE_WORKER, str(image_path)], capture_output=True, text=True, timeout=40)
        if proc.returncode == 0 and proc.stdout.strip():
            data = json.loads(proc.stdout.strip())
            if data.get("ok") and data.get("box"):
                box = tuple(data["box"])
                _PADDLE_CACHE[k] = (box, "stage_paddle_ocr")
                return box, "stage_paddle_ocr"
    except Exception:
        pass
    return None, "stage_paddle_not_found"

CURRENT_DETECTOR = "paddle_ocr"



# ─── Process Single Image ───
def process_image(image_path: Path, output_path: Path, timemark_text: str, y_override: int | None = None, x_override: int | None = None, schedule_lookup=None, asset_key=None, consensus_gy1: int | None = None, is_collage: bool = False, mask_mode: str | None = None, detector: str = "paddle_ocr", ignore_manual: bool = False) -> str:
    global CURRENT_DETECTOR
    actual_input_path = image_path
    if "03_photos_export" in str(image_path) or "03_export_foto" in str(image_path):
        try:
            parts = Path(image_path).parts
            folder_name = "03_photos_export" if "03_photos_export" in parts else ("03_export_foto" if "03_export_foto" in parts else None)
            if folder_name:
                idx = parts.index(folder_name)
                rel_p = Path(*parts[idx+1:])
                root_dir = Path(*parts[:idx]) if idx > 0 else Path(".")
                # Cek kandidat cropped temp di root ekspor yang sama terlebih dahulu
                cand_temp = root_dir / "03_photos_cropped_temp" / rel_p
                if not cand_temp.exists():
                    cand_temp = Path("03_photos_cropped_temp") / rel_p
                if cand_temp.exists():
                    actual_input_path = cand_temp
        except Exception:
            pass

    img_orig = Image.open(actual_input_path).convert("RGB")
    w, h = img_orig.size
    arr_orig = np.array(img_orig)

    eff_detector = detector or CURRENT_DETECTOR

    # Prioritas 1: Override manual (dari UI / parameter CLI) -> Bypass semua deteksi
    if y_override is not None:
        box_w = max(20, int(w * BOX_WIDTH_RATIO))
        box_h = max(10, int(h * BOX_HEIGHT_RATIO))
        if y_override <= 300:
            y1 = int((y_override / 300.0) * h)
        else:
            y1 = y_override

        if x_override is not None:
            if x_override <= 300:
                x1 = int((x_override / 300.0) * w)
            else:
                x1 = x_override
        else:
            x1 = int(w * 0.047)

        y1 = max(0, min(h - box_h, y1))
        x1 = max(0, min(w - box_w, x1))
        x2 = min(w, x1 + box_w)
        y2 = min(h, y1 + box_h)
        box = (x1, y1, x2, y2)
        stage = "stage_0_override"
        initial_box, initial_stage = box, stage
        # Simpan/perbarui koordinat manual ke .txt di folder sumber agar menjadi stok foto permanen
        _write_yolo_label(image_path, (w, h), box)
        if actual_input_path != image_path:
            _write_yolo_label(actual_input_path, (w, h), box)

    # Prioritas 2: Mode Mask Eksplisit (Pixel Inspector)
    elif mask_mode is not None:
        guide = find_guide_by_mask_direct(arr_orig, mask_mode)
        if guide is not None:
            box = place_textbox_fixed_offset(guide, w, h)
            stage = f"stage_pixel_inspector_{mask_mode}"
            _write_yolo_label(image_path, (w, h), guide)
        else:
            box, stage = locate_date_box(arr_orig, w, h, consensus_gy1=consensus_gy1, is_collage=is_collage)
        initial_box, initial_stage = box, stage

    # Prioritas 3: Deteksi otomatis (Google Vision / HSV Guide / OCR)
    else:
        if True:
            if eff_detector in ("paddle_ocr", "lama_ai"):
                p_box, p_stage = detect_timemark_via_paddle_ocr(actual_input_path, w, h)
                if p_box is not None:
                    # Snapping px1 to standard margin (14px) prevents duplicate day name
                    std_x1 = max(4, int(w * 0.047))
                    px1, py1, px2, py2 = p_box
                    if px1 > std_x1 and px1 < int(w * 0.35):
                        p_box = (std_x1, py1, max(px2, std_x1 + int(w * BOX_WIDTH_RATIO)), py2)
                    initial_box = p_box
                    initial_stage = p_stage
                else:
                    # Cek konsensus koordinat dari foto saudara (0.jpg / 100.jpg) dalam folder aset yang sama
                    sibling_box = None
                    try:
                        p_dir = actual_input_path.parent
                        for sib_name in ("0.txt", "100.txt", "50.txt"):
                            sib_txt = p_dir / sib_name
                            if sib_txt.exists() and sib_txt != actual_input_path.with_suffix(".txt"):
                                sib_b = _read_yolo_label(actual_input_path.with_name(sib_name.replace(".txt", ".jpg")), (w, h))
                                if sib_b is not None:
                                    sibling_box = sib_b
                                    break
                        if sibling_box is None:
                            meta_cand = output_path.parent / "meta.json"
                            if meta_cand.exists():
                                with open(meta_cand, "r", encoding="utf-8") as mf:
                                    mdata = json.load(mf)
                                for s_key in ("0.jpg", "100.jpg", "50.jpg"):
                                    if s_key in mdata and mdata[s_key].get("yPos"):
                                        sy = int(round((mdata[s_key]["yPos"] / 300.0) * h))
                                        sx = int(round((mdata[s_key].get("xPos", 14) / 300.0) * w))
                                        sb_w = int(w * BOX_WIDTH_RATIO)
                                        sb_h = int(h * BOX_HEIGHT_RATIO)
                                        sibling_box = (sx, sy, min(w, sx + sb_w), min(h, sy + sb_h))
                                        break
                    except Exception:
                        pass

                    if sibling_box is not None:
                        initial_box = sibling_box
                        initial_stage = "stage_consensus_sibling"
                    else:
                        initial_box, initial_stage = locate_date_box(arr_orig, w, h, consensus_gy1=consensus_gy1, is_collage=is_collage)
            elif eff_detector == "google_vision":
                gv_box, gv_stage = detect_timemark_via_google_vision(actual_input_path, w, h, arr_orig=arr_orig, is_collage=is_collage)
                if gv_box is not None:
                    initial_box = gv_box
                    initial_stage = gv_stage
                elif gv_stage == "quota_exceeded":
                    print(json.dumps({
                        "type": "quota_exceeded",
                        "message": "Kuota Google Cloud Vision telah habis atau penagihan dinonaktifkan."
                    }), flush=True)
                    action = "continue_guide"
                    if sys.stdin.isatty():
                        ans = input("\n[PAUSE] Kuota Google Vision habis. Lanjutkan dengan Metode Biasa (Garis Merah)? [Y/n]: ").strip().lower()
                        action = "stop" if ans == "n" else "continue_guide"
                    else:
                        line = sys.stdin.readline().strip()
                        if line:
                            action = line
                    if action == "continue_guide":
                        print("  │   ├── ⚠️ [FALLBACK] Beralih ke Metode Biasa (Garis Panduan Merah)", flush=True)
                        CURRENT_DETECTOR = "guide"
                        initial_box, initial_stage = locate_date_box(arr_orig, w, h, consensus_gy1=consensus_gy1, is_collage=is_collage)
                    else:
                        print("  │   ├── 🛑 [STOP] Proses dihentikan pengguna karena kuota Google Vision habis.", flush=True)
                        sys.exit(42)
                else:
                    # Cek konsensus koordinat dari foto saudara (0.jpg / 100.jpg) dalam folder aset yang sama
                    sibling_box = None
                    try:
                        p_dir = actual_input_path.parent
                        for sib_name in ("0.txt", "100.txt", "50.txt"):
                            sib_txt = p_dir / sib_name
                            if sib_txt.exists() and sib_txt != actual_input_path.with_suffix(".txt"):
                                sib_b = _read_yolo_label(actual_input_path.with_name(sib_name.replace(".txt", ".jpg")), (w, h))
                                if sib_b is not None:
                                    sibling_box = sib_b
                                    break
                        if sibling_box is None:
                            meta_cand = output_path.parent / "meta.json"
                            if meta_cand.exists():
                                with open(meta_cand, "r", encoding="utf-8") as mf:
                                    mdata = json.load(mf)
                                for s_key in ("0.jpg", "100.jpg", "50.jpg"):
                                    if s_key in mdata and mdata[s_key].get("yPos"):
                                        sy = int(round((mdata[s_key]["yPos"] / 300.0) * h))
                                        sx = int(round((mdata[s_key].get("xPos", 14) / 300.0) * w))
                                        sb_w = int(w * BOX_WIDTH_RATIO)
                                        sb_h = int(h * BOX_HEIGHT_RATIO)
                                        sibling_box = (sx, sy, min(w, sx + sb_w), min(h, sy + sb_h))
                                        break
                    except Exception:
                        pass

                    if sibling_box is not None:
                        initial_box = sibling_box
                        initial_stage = "stage_consensus_sibling"
                    else:
                        initial_box, initial_stage = locate_date_box(arr_orig, w, h, consensus_gy1=consensus_gy1, is_collage=is_collage)
            else:
                initial_box, initial_stage = locate_date_box(arr_orig, w, h, consensus_gy1=consensus_gy1, is_collage=is_collage)

            box, stage = initial_box, initial_stage
            # Simpan hasil deteksi ke 0.txt / 50.txt / 100.txt untuk dipakai otomatis di kemudian hari
            guide_for_label = _detect_guideline_for_label(arr_orig, w, h, is_collage)
            if guide_for_label is not None:
                _write_yolo_label(image_path, (w, h), guide_for_label)
            elif stage != "stage_fallback" and box is not None:
                _write_yolo_label(image_path, (w, h), box)

    detector_meta = {
        "stage": initial_stage,
        "textboxBox": list(initial_box),
        "imageSize": [w, h],
        "detectedAt": datetime.now().isoformat(timespec="seconds")
    }

    # ── Fallback: no date detected → copy as-is, no edit (only for non-cropped photos) ──
    if stage == "stage_fallback" and not is_collage and actual_input_path == image_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(actual_input_path, output_path)
        if y_override is not None or x_override is not None:
            output_path.with_suffix(output_path.suffix + ".detector.json").write_text(json.dumps(detector_meta), encoding="utf-8")
        # Flag file: per-photo marker for merge step
        flag_path = output_path.with_suffix(output_path.suffix + ".unedited")
        flag_path.write_text("")
        try:
            meta_path = output_path.parent / "meta.json"
            folder_meta = {}
            if meta_path.exists():
                try:
                    with open(meta_path, "r", encoding="utf-8") as mf:
                        folder_meta = json.load(mf)
                except Exception:
                    folder_meta = {}
            pname = output_path.name
            if pname not in folder_meta:
                folder_meta[pname] = {}
            folder_meta[pname]["stage"] = "stage_fallback_skipped"
            folder_meta[pname]["detector"] = "guide"
            folder_meta[pname]["dateText"] = timemark_text
            folder_meta[pname]["updatedAt"] = datetime.now().isoformat()
            folder_meta[pname]["xPos"] = 14
            folder_meta[pname]["yPos"] = 220
            if not folder_meta[pname].get("manualEdit", False):
                folder_meta[pname]["needCorrection"] = True
            with open(meta_path, "w", encoding="utf-8") as mf:
                json.dump(folder_meta, mf, indent=2, ensure_ascii=False)
        except Exception:
            pass
        return "stage_fallback_skipped"

    x1, y1, x2, y2 = box

    # Calculate exact text width to fit textbox and avoid over-blurring
    font_size = max(9, min(160, int(w * 0.038)))
    font = get_font(font_size)
    dummy = ImageDraw.Draw(Image.new("L", (1, 1)))
    fit_stroke = 1 if font_size >= 28 else 0
    bbox = dummy.textbbox((0, 0), timemark_text, font=font, stroke_width=fit_stroke)
    tw = bbox[2] - bbox[0]
    pad_x = max(4, int(w * 0.010))
    fit_w = tw + (2 * pad_x)

    # Tighten box to fit text exactly (while ensuring old detected text is covered if wider)
    old_w = (x2 - x1) if (stage in ("stage_google_vision", "stage_paddle_ocr") and (x2 - x1) <= int(w * 0.40)) else 0
    box_w = max(fit_w, old_w)
    x2 = min(w, x1 + box_w)
    box = (x1, y1, x2, y2)

    clean_path = output_path.parent / (output_path.stem + ".clean.jpg")
    if not clean_path.exists() and image_path is not None:
        cand_c = image_path.parent / (image_path.stem + ".clean.jpg")
        if cand_c.exists():
            clean_path = cand_c
    is_lama_mode = (eff_detector in ("paddle_ocr", "lama_ai") or detector in ("paddle_ocr", "lama_ai"))

    if is_lama_mode:
        # ARSITEKTUR CLEAN BASE: Jika foto sudah pernah dibersihkan LaMa, gunakan langsung tanpa inpaint ulang
        arr_work = None
        if y_override is not None and clean_path.exists() and not ignore_manual:
            try:
                img_clean = Image.open(clean_path).convert("RGB")
                arr_work = np.array(img_clean)
            except Exception:
                arr_work = None

        if arr_work is None:
            # Foto belum memiliki clean base: jalankan LaMa inpainting pada area tanggal lama
            old_box = None
            if box is not None:
                old_box = box
            else:
                p_box, _ = detect_timemark_via_paddle_ocr(actual_input_path, w, h)
                if p_box is not None:
                    old_box = p_box
                else:
                    std_y1 = int((240 / 300.0) * h)
                    std_box_h = int(h * BOX_HEIGHT_RATIO)
                    old_box = (int(w * 0.047), std_y1, int(w * 0.047) + int(w * BOX_WIDTH_RATIO), min(h, std_y1 + std_box_h))

            arr_clean = arr_orig.copy()
            if old_box and old_box[3] > old_box[1] and old_box[2] > old_box[0]:
                ai_inp = lama_inpaint(arr_clean, old_box)
                if ai_inp is not None:
                    arr_clean = ai_inp
                    # Simpan foto dasar bersih (clean base) hanya jika LaMa benar-benar sukses inpainting
                    try:
                        clean_path.parent.mkdir(parents=True, exist_ok=True)
                        Image.fromarray(arr_clean).save(clean_path, quality=95, subsampling=0)
                    except Exception:
                        pass
                else:
                    # Jika inpainting gagal, hapus clean_path korup/lama jika ada agar tidak terkontaminasi teks lama
                    if clean_path.exists():
                        try:
                            clean_path.unlink()
                        except Exception:
                            pass
            arr_work = arr_clean

        img_erased = Image.fromarray(arr_work)
        # ARSITEKTUR TANGGAL KOSONG (Virtual Layer):
        # Saat diproses dengan LaMa, foto di folder 04 murni foto bersih tanpa teks (tanggal kosong).
        # Teks baru TIDAK ditempel ke file JPG saat proses LaMa, melainkan ditampilkan
        # sebagai layer virtual di UI dan baru akan ditempelkan secara fisik saat 'Merge PDF' atau klik 'Tempel Tanggal'.
        img_out = img_erased
    else:
        # Mode Non-LaMa (Google Vision / HSV): Pertahankan alur legacy
        arr_work = arr_orig.copy()
        if y_override is not None:
            std_y1 = int((220 / 300.0) * h)
            if abs(y1 - std_y1) > max(10, int(h * 0.02)):
                std_x1 = int(w * 0.047)
                std_box_w = int(w * BOX_WIDTH_RATIO)
                std_box_h = int(h * BOX_HEIGHT_RATIO)
                std_x2 = min(w, std_x1 + std_box_w)
                std_y2 = min(h, std_y1 + std_box_h)
                if std_y2 > std_y1 and std_x2 > std_x1:
                    old_crop = arr_work[std_y1:std_y2, std_x1:std_x2]
                    if old_crop.size > 0:
                        old_mask = np.ones((std_y2 - std_y1, std_x2 - std_x1), dtype=bool)
                        arr_work[std_y1:std_y2, std_x1:std_x2] = diffuse_fill(old_crop, old_mask, steps=60)

        if y2 > y1 and x2 > x1:
            crop = arr_work[y1:y2, x1:x2]
            mask_img = np.ones((y2 - y1, x2 - x1), dtype=bool)
            arr_work[y1:y2, x1:x2] = diffuse_fill(crop, mask_img, steps=60)

        img_erased = Image.fromarray(arr_work)
        img_out = draw_textbox(img_erased, box, timemark_text, no_bg=False)

    # Save
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img_out.save(output_path, quality=95, subsampling=0)
    unedited_flag = output_path.with_suffix(output_path.suffix + ".unedited")
    if unedited_flag.exists():
        unedited_flag.unlink()
    if y_override is not None or x_override is not None:
        output_path.with_suffix(output_path.suffix + ".detector.json").write_text(json.dumps(detector_meta), encoding="utf-8")

    # Update meta.json with accurate coordinates and needCorrection flag
    try:
        meta_path = output_path.parent / "meta.json"
        folder_meta = {}
        if meta_path.exists():
            try:
                with open(meta_path, "r", encoding="utf-8") as mf:
                    folder_meta = json.load(mf)
            except Exception:
                folder_meta = {}
        pname = output_path.name
        if pname not in folder_meta:
            folder_meta[pname] = {}
        folder_meta[pname]["stage"] = stage
        folder_meta[pname]["detector"] = "paddle_ocr" if stage == "stage_paddle_ocr" else ("google_vision" if stage == "stage_google_vision" else "guide")
        folder_meta[pname]["dateText"] = timemark_text
        folder_meta[pname]["updatedAt"] = datetime.now().isoformat()
        norm_x = int(round((box[0] / float(w)) * 300)) if w > 0 else box[0]
        norm_y = int(round((box[1] / float(h)) * 300)) if h > 0 else box[1]
        folder_meta[pname]["xPos"] = norm_x
        folder_meta[pname]["yPos"] = norm_y

        is_manual = False if ignore_manual else (folder_meta[pname].get("manualEdit", False) or (y_override is not None))
        if y_override is not None and not ignore_manual:
            folder_meta[pname]["manualEdit"] = True
            is_manual = True
        elif ignore_manual:
            folder_meta[pname]["manualEdit"] = False

        is_need_corr = False
        if not is_manual:
            if stage in ("stage_1c_guide_consensus", "stage_fallback", "stage_fallback_skipped"):
                is_need_corr = True
            elif stage == "stage_google_vision" and (norm_x > 25 and (box[2] - box[0]) < 55):
                is_need_corr = True
        folder_meta[pname]["needCorrection"] = is_need_corr

        with open(meta_path, "w", encoding="utf-8") as mf:
            json.dump(folder_meta, mf, indent=2, ensure_ascii=False)
    except Exception:
        pass

    return stage


def _collect_folder_consensus(input_dir: Path, all_jpgs: list[Path]) -> dict[tuple[str, str, str], int]:
    from collections import defaultdict
    folder_guides = defaultdict(list)

    for src in all_jpgs:
        rel = src.relative_to(input_dir)
        fkey = _folder_key_from_path(rel, input_dir)
        if not fkey:
            continue
        try:
            img = Image.open(src).convert('RGB')
            arr = np.array(img)
            guide = find_red_guide(arr)
            if guide:
                gx1, gy1, gx2, gy2 = guide
                folder_guides[fkey].append(gy1)
        except Exception:
            pass

    consensus = {}
    for fkey, gy1s in folder_guides.items():
        if len(gy1s) >= 2:
            gy1s.sort()
            median = gy1s[len(gy1s) // 2]
            if all(abs(g - median) <= 10 for g in gy1s):
                consensus[fkey] = median
    return consensus


def main(override_args=None):
    if override_args is None:
        parser = argparse.ArgumentParser(description="Edit timemark on photos (Fixed-offset + Folder Consensus)")
        parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Input photos folder")
        parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output photos folder")
        parser.add_argument("--date", type=str, help="Global date text (e.g. 'Sabtu, Apr 29 2026 08:00')")
        parser.add_argument("--schedule", type=Path, default=DEFAULT_SCHEDULE, help="schedule.json for per-photo timestamps")
        parser.add_argument("--y-override", type=int, help="Force Y position for textbox")
        parser.add_argument("--x-override", type=int, help="Force X position for textbox")
        parser.add_argument("--single-out", type=Path, help="Force specific single output file path")
        parser.add_argument("--clear-output", action="store_true", help="Clear output folder first")
        parser.add_argument("--tim-filter", type=int, help="Process only schedule entries for this Tim number")
        parser.add_argument("--red-mask", action="store_true", help="Run with Red Mask HSV priority")
        parser.add_argument("--cyan-mask", action="store_true", help="Run with Cyan Mask HSV priority")
        parser.add_argument("--custom-mask", action="store_true", help="Run with Custom Mask HSV priority")
        parser.add_argument("--detector", choices=["paddle_ocr", "lama_ai", "google_vision", "guide"], default="paddle_ocr", help="Detection method: paddle_ocr/lama_ai (default), google_vision, or guide")
        parser.add_argument("--no-time", action="store_true", help="Format watermark tanggal saja tanpa jam (HH:MM)")
        parser.add_argument("--ignore-manual", action="store_true", help="Abaikan koreksi manual sebelumnya dan deteksi ulang posisi via detektor")
        args = parser.parse_args()

        if not args.single_out and args.input.is_dir():
            from export_pdf_foto import discover_period_workspaces, split_export_base_and_subdir
            inp = args.input.resolve()
            export_base, _ = split_export_base_and_subdir(inp, "03_export_foto")
            has_direct_btp = any(d.is_dir() and d.name.upper().startswith("BTP") for d in inp.iterdir())
            sched_explicit = bool(args.schedule and args.schedule != DEFAULT_SCHEDULE and args.schedule.is_file())
            workspaces = [] if (has_direct_btp or sched_explicit) else discover_period_workspaces(export_base, "03_export_foto")
            if workspaces:
                print(f"[PERIODE] Terdeteksi {len(workspaces)} folder periode untuk Edit Timemark.", flush=True)
                for pref, m_root in workspaces:
                    m_in = m_root / "03_export_foto"
                    if not m_in.is_dir():
                        m_in = m_root / "03_photos_export"
                    print(f"\n── Periode: {pref} ──", flush=True)
                    sub_args = argparse.Namespace(**vars(args))
                    sub_args.input = m_in
                    sub_args.output = m_root / "04_photos_edited"
                    sub_args.schedule = m_root / "schedule.json"
                    main(override_args=sub_args)
                return
    else:
        args = override_args

    global CURRENT_DETECTOR
    CURRENT_DETECTOR = args.detector

    input_dir = args.input
    output_dir = args.output

    if args.clear_output and output_dir.exists():
        shutil.rmtree(output_dir, ignore_errors=True)

    schedule_lookup = None
    if args.schedule and args.schedule.exists():
        schedule_data = load_schedule(args.schedule)
        schedule_lookup = build_schedule_lookup(schedule_data, args.tim_filter, include_time=(not getattr(args, 'no_time', False)))

    date_text = args.date or ""  # empty if not provided; schedule_lookup handles dates

    if input_dir.is_file():
        all_jpgs = [input_dir]
    else:
        all_jpgs = list(input_dir.rglob("*.jpg"))

    # Reset per-aset di semua folder Tim_1..Tim_4 pada 04_photos_edited untuk aset yang diproses ulang
    if not args.single_out and not args.clear_output and input_dir.is_dir() and all_jpgs and output_dir.exists():
        _reset_asset_rels = set()
        for _jpg_p in all_jpgs:
            try:
                _rel_p = _jpg_p.relative_to(input_dir)
                _p_parts = _rel_p.parts
                if len(_p_parts) >= 4:
                    _reset_asset_rels.add(asset_output_dir(Path(""), _p_parts[-4], _p_parts[-3], _p_parts[-2]))
                elif len(_p_parts) == 3:
                    _reset_asset_rels.add(asset_output_dir(Path(""), "", _p_parts[0], _p_parts[1]))
            except Exception:
                pass
        _reset_count = 0
        for _asset_rel in _reset_asset_rels:
            for _tim_dir in ("Tim_1", "Tim_2", "Tim_3", "Tim_4", ""):
                _target_sub = (output_dir / _tim_dir / _asset_rel) if _tim_dir else (output_dir / _asset_rel)
                if _target_sub.exists():
                    shutil.rmtree(_target_sub, ignore_errors=True)
                    _reset_count += 1
        if _reset_count:
            print(f"[INFO] Reset {_reset_count} folder aset lama di 04_photos_edited (lintas Tim) sebelum rerun Step 4.", flush=True)

    cand_logs_dir = (input_dir.parent / "logs") if input_dir.is_dir() else Path("logs")
    logs_for_collages = cand_logs_dir if (cand_logs_dir / "cropped_collages.json").exists() else Path("logs")
    cropped_collages_set = load_cropped_collages_manifest(logs_dir=str(logs_for_collages))
    if cropped_collages_set:
        print(f"[INFO] Loaded collage manifest ({len(cropped_collages_set)} cropped collage photos registered)")
    folder_consensus = _collect_folder_consensus(input_dir, all_jpgs) if input_dir.is_dir() else {}

    ok = 0
    failed = 0
    skipped = 0
    stage_counts = {
        "stage_paddle_ocr": 0,
        "stage_0_override": 0,
        "stage_1c_guide_original": 0,
        "stage_2_invert_guide": 0,
        "stage_3_custom1_hsv": 0,
        "stage_1c_guide_consensus": 0,
        "stage_ocr_old_date": 0,
        "stage_google_vision": 0,
        "stage_fallback": 0,
        "stage_fallback_skipped": 0
    }
    stage_details = []
    failed_files = []
    missing_dates = []
    unedited_files = []  # Track unedited photos for Excel
    tim_mapping = {}  # photo_rel_path -> tim_n

    current_asset_folder = None
    asset_folder_count = 0
    total_all_jpgs = len(all_jpgs)

    for idx_jpg, src in enumerate(all_jpgs, 1):
        src_resolved = src.resolve()
        parts = src_resolved.parts
        if "03_photos_export" in parts:
            idx = parts.index("03_photos_export")
            rel = Path(*parts[idx+1:])
        elif "03_export_foto" in parts:
            idx = parts.index("03_export_foto")
            rel = Path(*parts[idx+1:])
        elif "03_photos_cropped_temp" in parts:
            idx = parts.index("03_photos_cropped_temp")
            rel = Path(*parts[idx+1:])
        else:
            try:
                rel = src.relative_to(DEFAULT_INPUT)
            except ValueError:
                try:
                    rel = src.relative_to(DEFAULT_INPUT.resolve())
                except ValueError:
                    rel = src.relative_to(input_dir) if input_dir.is_dir() else Path(src.name)
        parts = rel.parts
        # Flat structure: [BTP/]category/identifier/photo.jpg
        btp_shift = 1 if parts and parts[0].startswith("BTP") else 0
        if len(parts) < 3 + btp_shift:
            if args.single_out:
                # Fallback for single-out with manual date or custom path
                btp = "BTP BD" if "BTP BD" in str(src_resolved).upper() else "BTP JAK"
                cand_cat = src_resolved.parent.parent.name if len(src_resolved.parts) >= 3 else "ASET"
                category = cand_cat if cand_cat.lower() not in ("03_export_foto", "04_photos_edited", "03_photos_cropped_temp", "tim_1", "tim_2", "tim_3", "tim_4") else "ASET"
                identifier = src_resolved.parent.name
                photo_name = src_resolved.name
                asset_key = (btp, category, identifier, photo_name)
            else:
                failed_files.append({
                    "file": str(rel),
                    "asset_type": "",
                    "detail": "",
                    "photo": "",
                    "reason": "invalid_asset_path; expected BTP/category/identifier/photo.jpg",
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                })
                continue
        else:
            btp = parts[0] if btp_shift else "BTP JAK"
            category = parts[0 + btp_shift]
            identifier = normalize_schedule_identifier(parts[1 + btp_shift])
            photo_name = parts[2 + btp_shift]
            asset_key = (btp, category, identifier, photo_name)
        if args.tim_filter is not None and (not schedule_lookup or asset_key not in schedule_lookup):
            continue

        tim_n = 1
        if args.date:
            timemark_text = args.date
            dst_dir = output_dir / f"Tim_{tim_n}"
        elif schedule_lookup and asset_key:
            result = schedule_lookup.get(asset_key)
            if not result:
                base_ident = _strip_date_suffix(identifier)
                if base_ident != identifier:
                    result = schedule_lookup.get((btp, category, base_ident, photo_name))
            if result:
                timemark_text, tim_n = result
                dst_dir = output_dir / f"Tim_{tim_n}" / asset_output_dir(Path(""), btp, category, identifier)
            else:
                # Schedule exists but this photo not in it — try date.txt fallback
                folder_date = _read_date_txt(input_dir, btp, category, identifier)
                if folder_date:
                    dt = parse_date_text(folder_date)
                    if dt:
                        pct = 0
                        name_stem = Path(photo_name).stem
                        if name_stem == "50": pct = 50
                        elif name_stem == "100": pct = 100
                        duration = CATEGORY_DURATIONS.get(category.upper(), DEFAULT_DURATION)
                        offset_minutes = int(pct * duration / 100)
                        photo_dt = dt + timedelta(minutes=offset_minutes)
                        timemark_text = format_timemark(photo_dt)
                        dst_dir = output_dir / f"Tim_{tim_n}" / asset_output_dir(Path(""), btp, category, identifier)
                    else:
                        print(f"  │   ├── ⚠️ [WARN] Dilewati ({rel.parent}): date.txt tidak terbaca ('{folder_date}')", flush=True)
                        missing_dates.append({"folder": str(rel.parent), "btp": btp, "category": category, "identifier": identifier, "reason": "date.txt unreadable"})
                        skipped += 1
                        continue
                else:
                    # Fallback date if not in schedule & no date.txt
                    timemark_text = date_text or format_timemark(datetime.now())
                    dst_dir = output_dir / f"Tim_{tim_n}" / asset_output_dir(Path(""), btp, category, identifier)
        else:
            # No schedule — try date.txt
            folder_date = _read_date_txt(input_dir, btp, category, identifier)
            if folder_date:
                dt = parse_date_text(folder_date)
                if dt:
                    pct = 0
                    name_stem = Path(photo_name).stem
                    if name_stem == "50": pct = 50
                    elif name_stem == "100": pct = 100
                    duration = CATEGORY_DURATIONS.get(category.upper(), DEFAULT_DURATION)
                    offset_minutes = int(pct * duration / 100)
                    photo_dt = dt + timedelta(minutes=offset_minutes)
                    timemark_text = format_timemark(photo_dt)
                    dst_dir = output_dir / f"Tim_{tim_n}" / asset_output_dir(Path(""), btp, category, identifier)
                else:
                    timemark_text = date_text or format_timemark(datetime.now())
                    dst_dir = output_dir / f"Tim_{tim_n}" / asset_output_dir(Path(""), btp, category, identifier)
            else:
                timemark_text = date_text or format_timemark(datetime.now())
                dst_dir = output_dir / f"Tim_{tim_n}" / asset_output_dir(Path(""), btp, category, identifier)
        if args.no_time and timemark_text:
            timemark_text = re.sub(r"\s+\d{2}:\d{2}$", "", timemark_text.strip())
        tim_mapping[str(rel)] = tim_n
        dst = args.single_out if args.single_out else (dst_dir / src.name)
        meta_lookup_dir = dst.parent if args.single_out else dst_dir
        # ponytail: batch mode ignores stale dst meta.json so detector runs cleanly
        if args.single_out:
            manual_meta = {} if args.ignore_manual else _read_manual_meta(meta_lookup_dir, photo_name)
            if not manual_meta and not args.ignore_manual and src.parent != meta_lookup_dir:
                manual_meta = _read_manual_meta(src.parent, photo_name)
        else:
            manual_meta = {} if args.ignore_manual else _read_manual_meta(src.parent, photo_name)
        # Prioritaskan argumen CLI eksplisit (--y-override / --x-override) dari aksi user
        if args.y_override is not None:
            photo_y_override = args.y_override
        elif manual_meta and "yPos" in manual_meta:
            photo_y_override = manual_meta["yPos"]
        else:
            photo_y_override = None

        if args.x_override is not None:
            photo_x_override = args.x_override
        elif manual_meta and "xPos" in manual_meta:
            photo_x_override = manual_meta["xPos"]
        else:
            photo_x_override = None

        fkey = _folder_key_from_path(rel, input_dir)
        consensus_gy1 = folder_consensus.get(fkey) if fkey else None

        # Smart sibling consensus: jika single-file run atau folder consensus tidak ada
        if consensus_gy1 is None:
            # 1. Cek meta.json di folder output atau folder sumber
            for check_dir in [meta_lookup_dir, src.parent]:
                m_file = check_dir / "meta.json"
                if m_file.exists():
                    try:
                        with open(m_file, "r", encoding="utf-8") as mf:
                            m_data = json.load(mf)
                        for sib_name, sib_info in m_data.items():
                            if sib_name != photo_name and isinstance(sib_info, dict) and "yPos" in sib_info:
                                sib_y = sib_info["yPos"]
                                try:
                                    with Image.open(src) as _im_check:
                                        _chk_h = _im_check.height
                                except Exception:
                                    _chk_h = 300
                                consensus_gy1 = int((sib_y / 300.0) * _chk_h)
                                break
                    except Exception:
                        pass
                if consensus_gy1 is not None:
                    break

            # 2. Cek label YOLO .txt dari sibling di folder sumber (misal 0.txt / 50.txt)
            if consensus_gy1 is None and src.parent.exists():
                for sib_txt in ["0.txt", "50.txt", "100.txt"]:
                    if sib_txt != f"{Path(photo_name).stem}.txt":
                        st_p = src.parent / sib_txt
                        if st_p.exists():
                            try:
                                parts = st_p.read_text(encoding="utf-8").strip().split()
                                if len(parts) >= 5:
                                    cy = float(parts[2])
                                    try:
                                        with Image.open(src) as _im_check:
                                            _chk_h = _im_check.height
                                    except Exception:
                                        _chk_h = 300
                                    consensus_gy1 = int(cy * _chk_h)
                                    break
                            except Exception:
                                pass

        asset_folder_key = (btp, category, identifier, tim_n)
        if asset_folder_key != current_asset_folder:
            if current_asset_folder is not None:
                print(f"  └── [OK] Folder selesai diproses\n", flush=True)
            current_asset_folder = asset_folder_key
            asset_folder_count += 1
            print(f"[{idx_jpg}/{total_all_jpgs}] 📁 [Folder #{asset_folder_count}] {btp}/{category}/{identifier} (Tim {tim_n})", flush=True)
            print(f"  ├── Target Timemark : {timemark_text}", flush=True)

        is_coll = str(rel).replace('\\', '/').lower() in cropped_collages_set
        try:
            mask_mode = "red" if args.red_mask else "cyan" if args.cyan_mask else "custom" if args.custom_mask else None
            stage = process_image(src, dst, timemark_text, photo_y_override, photo_x_override, schedule_lookup, asset_key, consensus_gy1, is_collage=is_coll, mask_mode=mask_mode, detector=CURRENT_DETECTOR, ignore_manual=getattr(args, 'ignore_manual', False))
            ok += 1
            if stage in stage_counts:
                stage_counts[stage] += 1
            stage_details.append({
                "file": str(rel),
                "stage": stage,
                "asset_type": category,
                "detail": identifier,
                "photo": photo_name,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            # Track unedited fallbacks for Excel log
            if stage == "stage_fallback_skipped":
                unedited_files.append({
                    "btp": btp,
                    "category": category,
                    "identifier": identifier,
                    "photo": photo_name,
                    "source": str(src),
                    "output": str(dst),
                    "stage": stage,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
            print(f"  │   ├── {photo_name} -> [{stage}] Watermark diaplikasikan", flush=True)
            print(json.dumps({
                "type": "stage",
                "file": str(rel),
                "stage": stage,
                "asset_type": category,
                "detail": identifier,
                "photo": photo_name
            }), flush=True)
        except Exception as e:
            print(f"  │   ├── ❌ [ERROR] {photo_name} gagal: {e}", flush=True)
            failed += 1
            failed_files.append({
                "file": str(rel),
                "asset_type": category,
                "detail": identifier,
                "photo": photo_name,
                "reason": str(e),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })

    if current_asset_folder is not None:
        print(f"  └── [OK] Folder selesai diproses\n", flush=True)



    logs_dir = Path("logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    
    # Write tim_mapping.json if schedule was used
    if args.schedule and tim_mapping:
        tim_mapping_data = {
            "version": 1,
            "generated_at": datetime.now().isoformat(),
            "mapping": tim_mapping,
            "tims_used": sorted(set(tim_mapping.values()))
        }
        with open(logs_dir / "tim_mapping.json", "w", encoding="utf-8") as f:
            json.dump(tim_mapping_data, f, indent=2, ensure_ascii=False)

    if not args.single_out and stage_details:
        try:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Stage Details"
            headers = ["File", "Stage", "Asset Type", "Detail Aset", "Photo", "Timestamp"]
            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col, value=header)
                cell.font = Font(bold=True)
                cell.fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
                cell.font = Font(bold=True, color="FFFFFF")
            for row_idx, item in enumerate(stage_details, 2):
                ws.cell(row=row_idx, column=1, value=item["file"])
                ws.cell(row=row_idx, column=2, value=item["stage"])
                ws.cell(row=row_idx, column=3, value=item["asset_type"])
                ws.cell(row=row_idx, column=4, value=item["detail"])
                ws.cell(row=row_idx, column=5, value=item["photo"])
                ws.cell(row=row_idx, column=6, value=item["timestamp"])
            for col in ws.columns:
                max_length = max(len(str(cell.value)) if cell.value else 0 for cell in col)
                ws.column_dimensions[col[0].column_letter].width = max_length + 2
            wb.save(logs_dir / "edit_stages.xlsx")
        except Exception:
            pass

    if not args.single_out and failed_files:
        try:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Failed Files"
            headers = ["File", "Asset Type", "Detail Aset", "Photo", "Alasan", "Timestamp"]
            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col, value=header)
                cell.font = Font(bold=True)
                cell.fill = PatternFill(start_color="FF4444", end_color="FF4444", fill_type="solid")
                cell.font = Font(bold=True, color="FFFFFF")
            for row_idx, item in enumerate(failed_files, 2):
                ws.cell(row=row_idx, column=1, value=item["file"])
                ws.cell(row=row_idx, column=2, value=item["asset_type"])
                ws.cell(row=row_idx, column=3, value=item["detail"])
                ws.cell(row=row_idx, column=4, value=item["photo"])
                ws.cell(row=row_idx, column=5, value=item["reason"])
                ws.cell(row=row_idx, column=6, value=item["timestamp"])
            for col in ws.columns:
                max_length = max(len(str(cell.value)) if cell.value else 0 for cell in col)
                ws.column_dimensions[col[0].column_letter].width = max_length + 2
            wb.save(logs_dir / "edit_failed.xlsx")
            (logs_dir / "edit_failed.json").write_text(json.dumps(failed_files, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    if not args.single_out and missing_dates:
        try:
            # Deduplicate by folder
            seen_folders = set()
            unique_missing = []
            for item in missing_dates:
                if item["folder"] not in seen_folders:
                    seen_folders.add(item["folder"])
                    unique_missing.append(item)
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Missing Dates"
            headers = ["Folder", "BTP", "Category", "Identifier", "Alasan"]
            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col, value=header)
                cell.font = Font(bold=True)
                cell.fill = PatternFill(start_color="FF8800", end_color="FF8800", fill_type="solid")
                cell.font = Font(bold=True, color="FFFFFF")
            for row_idx, item in enumerate(unique_missing, 2):
                ws.cell(row=row_idx, column=1, value=item["folder"])
                ws.cell(row=row_idx, column=2, value=item["btp"])
                ws.cell(row=row_idx, column=3, value=item["category"])
                ws.cell(row=row_idx, column=4, value=item["identifier"])
                ws.cell(row=row_idx, column=5, value=item["reason"])
            for col in ws.columns:
                max_length = max(len(str(cell.value)) if cell.value else 0 for cell in col)
                ws.column_dimensions[col[0].column_letter].width = max_length + 2
            wb.save(logs_dir / "missing_dates.xlsx")
        except Exception:
            pass
        (logs_dir / "missing_dates.json").write_text(json.dumps(unique_missing, indent=2, ensure_ascii=False), encoding="utf-8")

    if unedited_files:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Unedited Photos"
        headers = ["BTP", "Category", "Identifier/Aset", "Foto", "Stage", "Source Path", "Output Path", "Timestamp"]
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = Font(bold=True)
            cell.fill = PatternFill(start_color="FF8800", end_color="FF8800", fill_type="solid")
            cell.font = Font(bold=True, color="FFFFFF")
        for row_idx, item in enumerate(unedited_files, 2):
            ws.cell(row=row_idx, column=1, value=item["btp"])
            ws.cell(row=row_idx, column=2, value=item["category"])
            ws.cell(row=row_idx, column=3, value=item["identifier"])
            ws.cell(row=row_idx, column=4, value=item["photo"])
            ws.cell(row=row_idx, column=5, value=item.get("stage", "stage_fallback_skipped"))
            ws.cell(row=row_idx, column=6, value=item["source"])
            ws.cell(row=row_idx, column=7, value=item["output"])
            ws.cell(row=row_idx, column=8, value=item["timestamp"])
        for col in ws.columns:
            max_length = max(len(str(cell.value)) if cell.value else 0 for cell in col)
            ws.column_dimensions[col[0].column_letter].width = max_length + 2
        wb.save(logs_dir / "unedited_photos.xlsx")
        (logs_dir / "unedited_photos.json").write_text(json.dumps(unedited_files, indent=2, ensure_ascii=False), encoding="utf-8")

    summary = {
        "step": "edit",
        "success": ok,
        "failed": failed,
        "skipped": skipped,
        "missing_dates": len(unique_missing) if missing_dates else 0,
        "stage_counts": stage_counts,
        "failed_file": "logs/edit_failed.xlsx" if failed_files else None,
        "stages_file": "logs/edit_stages.xlsx" if stage_details else None,
        "missing_dates_file": "logs/missing_dates.xlsx" if missing_dates else None
    }
    if total_all_jpgs == 0:
        print(f"⚠️ [WARN] Tidak ada berkas foto .jpg ditemukan di: {input_dir}", flush=True)
    print(f"📊 Ringkasan Step 4: {ok} berhasil, {skipped} dilewati, {failed} gagal.", flush=True)
    print(f"__SUMMARY__:{json.dumps(summary)}", flush=True)
    if total_all_jpgs > 0 and ok == 0 and (failed > 0 or bool(missing_dates)):
        print(f"❌ [ERROR] Step 4 gagal memproses seluruh foto ({skipped} dilewati, {failed} gagal). Menghentikan pipeline agar tidak lanjut ke Step 5.", flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
