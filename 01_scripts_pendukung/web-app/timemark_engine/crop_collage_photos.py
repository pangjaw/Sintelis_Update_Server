import os
import sys
import json
from pathlib import Path
import numpy as np
from PIL import Image


# ── Tuning constants for 300x300 images ────────────────────────────────────
CROSSHAIR_SEARCH_RANGE  = (0.35, 0.65)   # divider must be in 35–65% of image (middle zone)
CROSSHAIR_MIN_PROMINENCE = 8.0            # row/col peak brightness must exceed local bg by at least 8.0
CROSSHAIR_MIN_BRIGHTNESS = 135.0          # row/col peak mean brightness must be >= 135
CROSSHAIR_CENTER_BRIGHT  = 170.0          # intersection pixel brightness threshold


def _brightness_profile(arr: np.ndarray, axis: int) -> np.ndarray:
    """Return mean brightness profile along an axis (axis=0→row profile, axis=1→col profile)."""
    return np.mean(arr, axis=(1 - axis, 2))


def _find_divider(profile: np.ndarray, search_lo: float = 0.35, search_hi: float = 0.65) -> tuple[int, float, float]:
    """Find peak row/column in the central search range with prominence calculation."""
    n = len(profile)
    lo = int(n * search_lo)
    hi = int(n * search_hi)
    if lo >= hi:
        return n // 2, 0.0, 0.0

    sub = profile[lo:hi]
    rel_idx = int(np.argmax(sub))
    peak_idx = lo + rel_idx
    peak_val = float(profile[peak_idx])

    # Local background: average of regions outside 35px around peak
    bg_lo = profile[max(0, peak_idx - 35): max(0, peak_idx - 12)]
    bg_hi = profile[min(n, peak_idx + 12): min(n, peak_idx + 35)]
    bg = float(np.mean(np.concatenate([bg_lo, bg_hi]))) if (len(bg_lo) + len(bg_hi)) > 0 else 0.0
    prom = peak_val - bg

    return peak_idx, peak_val, prom


def detect_collage_by_crosshair(img: Image.Image) -> tuple[bool, int, int, str]:
    """Detects 2x2 collage in 300x300 images by checking center crosshair prominence and brightness.
    Returns (is_collage, peak_x, peak_y, reason).
    """
    w, h = img.size
    arr = np.array(img.convert('RGB')).astype(np.float32)
    gray = np.mean(arr, axis=2)

    # 1. Search peak row & col in 35%..65% range
    row_means = np.mean(gray, axis=1)
    col_means = np.mean(gray, axis=0)

    peak_y, peak_y_val, prom_y = _find_divider(row_means, *CROSSHAIR_SEARCH_RANGE)
    peak_x, peak_x_val, prom_x = _find_divider(col_means, *CROSSHAIR_SEARCH_RANGE)

    # Intersection brightness
    center_val = float(np.mean(gray[max(0, peak_y-3):peak_y+4, max(0, peak_x-3):peak_x+4]))

    # Detection logic:
    # A. Both Y and X have prominent bright lines (prom >= 8, val >= 135)
    # B. Center intersection is very bright (center_val >= 170) with prom >= 5
    is_coll = (prom_y >= CROSSHAIR_MIN_PROMINENCE and prom_x >= CROSSHAIR_MIN_PROMINENCE and peak_y_val >= CROSSHAIR_MIN_BRIGHTNESS and peak_x_val >= CROSSHAIR_MIN_BRIGHTNESS) or \
              (center_val >= CROSSHAIR_CENTER_BRIGHT and prom_y >= 5.0 and prom_x >= 5.0)

    reason = (
        f"Crosshair Y: y={peak_y}(val={peak_y_val:.0f}, prom={prom_y:.1f}) | "
        f"X: x={peak_x}(val={peak_x_val:.0f}, prom={prom_x:.1f}) | "
        f"center={center_val:.0f} -> {'KOLASE' if is_coll else 'Bukan Kolase'}"
    )

    return is_coll, peak_x, peak_y, reason


def get_crop_box_bottom_left(img: Image.Image) -> tuple[int, int, int, int]:
    """Find bottom-left quadrant using crosshair peak coordinates.
    Returns (left, upper, right, lower) pixel coordinates.
    """
    w, h = img.size
    _, peak_x, peak_y, _ = detect_collage_by_crosshair(img)

    # Clamp to valid range
    peak_y = max(int(h * 0.25), min(int(h * 0.75), peak_y))
    peak_x = max(int(w * 0.25), min(int(w * 0.75), peak_x))

    # Bottom-left quadrant (1:1 square): x in [0, side], y in [h - side, h]
    bw = peak_x
    bh = h - peak_y
    side = max(1, min(bw, bh))
    return (0, h - side, side, h)


def is_collage_photo_adaptive(img: Image.Image) -> tuple[bool, int, int, str]:
    """Detects if an image is a 2x2 collage photo using center crosshair detection.
    Returns: (is_collage: bool, divider_x: int, divider_y: int, reason: str)
    NOTE: Used by analyzer.py to flag uncropped collages as HIGH RISK.
    """
    is_coll, peak_x, peak_y, reason = detect_collage_by_crosshair(img)
    return is_coll, peak_x, peak_y, reason


def process_collage_photos(photos_dir: str = "03_photos_export", logs_dir: str = "logs"):
    """Auto-cropping is DISABLED. User crops via the Collage Analyzer UI sub-tab."""
    print("[INFO] Auto-crop disabled. Use the Collage Analyzer tab in the dashboard to crop manually.")

    logs_root = Path(logs_dir)
    logs_root.mkdir(parents=True, exist_ok=True)
    log_json = logs_root / "cropped_collages.json"
    existing = []
    if log_json.exists():
        try:
            with open(log_json, 'r', encoding='utf-8') as f:
                existing = json.load(f)
        except Exception:
            existing = []
    if not existing:
        with open(log_json, 'w', encoding='utf-8') as f:
            json.dump([], f, indent=2)
    print(f"[INFO] Collage manifest: {log_json} ({len(existing)} entries)")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Step 1.5: Collage detection helper (AUTO-CROP DISABLED - use UI)")
    parser.add_argument("--photos-dir", default="03_photos_export", help="Path to photos export root")
    parser.add_argument("--logs-dir",   default="logs",            help="Path to logs directory")
    parser.add_argument("--scan",       action="store_true",       help="Scan and print detected collages")
    args = parser.parse_args()

    if args.scan:
        root = Path(args.photos_dir)
        found = 0
        for p in sorted(root.glob("**/*.jpg")):
            try:
                img = Image.open(p)
                is_coll, _, _, reason = is_collage_photo_adaptive(img)
                if is_coll:
                    print(f"  [COLLAGE] {p.relative_to(root)} — {reason}")
                    found += 1
            except Exception as e:
                print(f"  [ERR] {p}: {e}")
        print(f"\nTotal: {found} collages found.")
    else:
        process_collage_photos(args.photos_dir, args.logs_dir)
