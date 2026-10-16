#!/usr/bin/env python3
"""edit_photo_coordinate_only.py — Tempel koordinat GPS di pojok kiri atas foto.

Input: 03_photos_export (atau 03_photos_cropped_temp jika foto kolase).
Mapping: config/asset_koordinat_mapping.json (dari Excel Timemark_F.xlsx).
Jadwal: schedule.json (dari Step 3 Scheduler untuk penentuan Tim 1 / Tim 2).
Output: 04_koordinat/Tim_N/{btp}/{category}/{identifier}/{photo}.jpg
"""

import os
import sys
import json
import re
import argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

DEFAULT_EXPORT_DIR = Path("03_photos_export")
DEFAULT_TEMP_DIR = Path("03_photos_cropped_temp")
DEFAULT_OUTPUT_DIR = Path("04_koordinat")
DEFAULT_SCHEDULE_FILE = Path("schedule.json")
DEFAULT_MAPPING_FILE = Path("config/asset_koordinat_mapping.json")

_FONT_CACHE = {}


def get_font(size: int):
    """Load and cache font with fallback to standard system fonts."""
    if size in _FONT_CACHE:
        return _FONT_CACHE[size]
    candidates = [
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "arialbd.ttf",
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "arial.ttf",
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "segoeuib.ttf",
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "segoeui.ttf",
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "calibrib.ttf",
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "calibri.ttf",
        "DejaVuSans-Bold.ttf",
        "DejaVuSans.ttf",
    ]
    for fp in candidates:
        if isinstance(fp, str):
            try:
                font = ImageFont.truetype(fp, size=size)
                _FONT_CACHE[size] = font
                return font
            except Exception:
                continue
        elif fp.exists():
            try:
                font = ImageFont.truetype(str(fp), size=size)
                _FONT_CACHE[size] = font
                return font
            except Exception:
                continue
    font = ImageFont.load_default()
    _FONT_CACHE[size] = font
    return font


def load_schedule(path: Path):
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def load_mapping(path: Path):
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def normalize_identifier(identifier: str) -> str:
    s = identifier.strip().upper()
    # Strip date suffix if present (e.g. W13 BOO_02-02 -> W13 BOO)
    s = re.sub(r'_\d{2}-\d{2}$', '', s)
    if s == "ZP 41B BOO":
        return "ZP 41 BOO"
    return s


def build_schedule_lookup(schedule_data: dict, tim_filter: int | None = None):
    """Build lookup: (btp, category, identifier, photo_stem) -> (tim_n, funcloc)."""
    lookup = {}
    for sched in schedule_data.get("schedules", []):
        tim_n = sched.get("tim", 1)
        if tim_filter is not None and tim_n != tim_filter:
            continue
        btp = sched.get("btp", "BTP JAK")
        category = sched.get("category", "UNKNOWN")
        identifier = normalize_identifier(sched.get("identifier") or sched.get("pdf_stem", ""))
        funcloc = sched.get("funcloc", "")

        for pname in sched.get("photos", {}).keys():
            key = (btp, category, identifier, pname)
            existing = lookup.get(key)
            if existing is None or tim_n > existing[0]:
                lookup[key] = (tim_n, funcloc)
    return lookup


def resolve_coordinate(
    identifier: str,
    funcloc: str,
    mapping_data: dict,
    coord_override: str | None = None,
    category: str | None = None
) -> str | None:
    """Find coordinate string from mapping data."""
    if coord_override and coord_override.strip():
        return coord_override.strip()

    if not mapping_data:
        return None

    by_funcloc = mapping_data.get("by_funcloc", {})
    by_identifier = mapping_data.get("by_identifier", {})
    by_nokai = mapping_data.get("by_nokai", {})

    # 1. Try by funcloc code (e.g. AXL11636)
    if funcloc:
        floc_code = funcloc.split(":")[0].strip().upper()
        if floc_code in by_funcloc:
            return by_funcloc[floc_code].get("coordinate")

    # 2. Try by exact identifier (or base identifier without _DD-MM suffix)
    norm_ident = normalize_identifier(identifier)
    base_ident = re.sub(r'_\d{2}-\d{2}$', '', norm_ident)
    if norm_ident in by_identifier:
        return by_identifier[norm_ident].get("coordinate")
    if base_ident in by_identifier:
        return by_identifier[base_ident].get("coordinate")

    # 3. Try alias with or without leading zeroes for JPL (e.g. JPL 2 BOO <-> JPL 02 BOO)
    jpl_clean = re.sub(r'\bJPL\s+0+(\d+)', r'JPL \1', norm_ident)
    if jpl_clean in by_identifier:
        return by_identifier[jpl_clean].get("coordinate")
    jpl_zero = re.sub(r'\bJPL\s+(\d)\b', r'JPL 0\1', norm_ident)
    if jpl_zero in by_identifier:
        return by_identifier[jpl_zero].get("coordinate")

    # 4. Search in description / no_kai
    clean_search = re.sub(r'[^A-Z0-9]', '', norm_ident)
    for k, v in by_identifier.items():
        if clean_search == re.sub(r'[^A-Z0-9]', '', k):
            return v.get("coordinate")

    # 5. Fallback aliases
    if norm_ident == "CLT" and (category == "CATUDAYA" or not category):
        if "CDA10151" in by_funcloc:
            return by_funcloc["CDA10151"].get("coordinate")
        return "-6.530543, 106.800952"

    if norm_ident in ("MJ20 CLT", "MJ20") or clean_search in ("MJ20CLT", "MJ20"):
        if "SIN11782" in by_funcloc:
            return by_funcloc["SIN11782"].get("coordinate")
        return "-6.527237, 106.800950"

    return None


def draw_top_left_coordinate(
    img: Image.Image,
    coord_text: str,
    x_override: int | None = None,
    y_override: int | None = None,
    font_size: int | None = None,
    opacity: int = 140,
    margin_left: int = 8,
    margin_top: int = 8,
) -> tuple[Image.Image, dict]:
    """Draws white GPS coordinate text at the top-left with semi-transparent black background."""
    w, h = img.size

    # Calculate font size: default ~14-16px for 300x300 image
    if font_size is None or font_size <= 0:
        font_size = max(10, min(80, int(w * 0.048)))
    font = get_font(font_size)

    # Measure text
    dummy = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    bbox = dummy.textbbox((0, 0), coord_text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]

    pad_x = max(4, int(w * 0.015))
    pad_y = max(2, int(h * 0.008))
    box_w = tw + (2 * pad_x)
    box_h = th + (2 * pad_y)

    # Determine position (top-left default)
    if x_override is not None and y_override is not None:
        x1 = max(0, min(w - box_w, int(x_override)))
        y1 = max(0, min(h - box_h, int(y_override)))
    else:
        x1 = max(0, margin_left)
        y1 = max(0, margin_top)

    x2 = min(w, x1 + box_w)
    y2 = min(h, y1 + box_h)

    # Create overlay for semi-transparent rounded rectangle
    out = img.convert("RGBA").copy()
    overlay = Image.new("RGBA", out.size, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)

    radius = max(3, int(box_h * 0.2))
    fill_color = (0, 0, 0, max(0, min(255, opacity)))
    odraw.rounded_rectangle((x1, y1, x2, y2), radius=radius, fill=fill_color)

    # Composite background overlay
    out = Image.alpha_composite(out, overlay)

    # Draw sharp white text on top
    draw = ImageDraw.Draw(out)
    text_x = x1 + pad_x - bbox[0]
    text_y = y1 + pad_y - bbox[1]
    draw.text((text_x, text_y), coord_text, fill=(255, 255, 255, 255), font=font)

    meta_info = {
        "coordText": coord_text,
        "xPos": x1,
        "yPos": y1,
        "box": [x1, y1, x2, y2],
        "fontSize": font_size,
        "opacity": opacity,
        "imageSize": [w, h]
    }
    return out.convert("RGB"), meta_info


def process_single_photo(
    rel_path: str,
    export_dir: Path,
    temp_dir: Path,
    output_dir: Path,
    schedule_lookup: dict,
    mapping_data: dict,
    coord_override: str | None = None,
    x_override: int | None = None,
    y_override: int | None = None,
    font_size: int | None = None,
    opacity: int = 140,
    forced_tim: int | None = None,
) -> bool:
    """Processes 1 photo, stamps GPS coordinate, saves to 04_koordinat/Tim_N/..."""
    norm_rel = rel_path.replace("\\", "/").strip("/")
    parts = norm_rel.split("/")
    if len(parts) < 4:
        print(f"[SKIP] Invalid asset path (must be BTP/category/detail/photo.jpg): {norm_rel}", file=sys.stderr)
        return False

    btp = parts[0]
    category = parts[1]
    identifier = "/".join(parts[2:-1])
    photo_name = parts[-1]
    photo_stem = Path(photo_name).stem

    # 1. Resolve source image: priority temp cropped -> export original
    temp_file = temp_dir / norm_rel
    export_file = export_dir / norm_rel
    if temp_file.exists():
        src_path = temp_file
    elif export_file.exists():
        src_path = export_file
    else:
        print(f"[SKIP] Source file not found: {norm_rel}", file=sys.stderr)
        return False

    # 2. Determine tim group & funcloc
    clean_ident = normalize_identifier(identifier)
    lookup_key = (btp, category, clean_ident, photo_name)
    alt_lookup_key = (btp, category, clean_ident, photo_stem)
    sched_info = schedule_lookup.get(lookup_key) or schedule_lookup.get(alt_lookup_key)

    if forced_tim is not None:
        tim_n = forced_tim
    elif sched_info:
        tim_n = sched_info[0]
    else:
        tim_n = 1

    funcloc = sched_info[1] if sched_info else ""
    if not funcloc:
        for (b, c, ident, _), (t_val, f_val) in schedule_lookup.items():
            if ident == clean_ident and f_val:
                funcloc = f_val
                break

    coord_text = resolve_coordinate(identifier, funcloc, mapping_data, coord_override=coord_override, category=category)
    if not coord_text:
        print(f"  │   ├── ⚠️ [SKIP] Koordinat tidak ditemukan untuk '{identifier}' (dilewati)", flush=True)
        return None

    # Check for existing manual edit meta.json
    out_folder = output_dir / f"Tim_{tim_n}" / btp / category / identifier
    meta_path = out_folder / "meta.json"
    if meta_path.exists() and (x_override is None or y_override is None):
        try:
            with open(meta_path, "r", encoding="utf-8") as mf:
                existing_meta = json.load(mf)
                p_meta = existing_meta.get("photos", {}).get(photo_name, {})
                if p_meta.get("manualEdit"):
                    if x_override is None:
                        x_override = p_meta.get("xPos")
                    if y_override is None:
                        y_override = p_meta.get("yPos")
                    if font_size is None:
                        font_size = p_meta.get("fontSize")
                    if opacity == 140 and "opacity" in p_meta:
                        opacity = p_meta.get("opacity")
                    if not coord_override and p_meta.get("coordText"):
                        coord_text = p_meta.get("coordText")
        except Exception:
            pass

    # 4. Open image and stamp coordinate
    try:
        with Image.open(src_path) as orig_img:
            stamped_img, meta_info = draw_top_left_coordinate(
                orig_img,
                coord_text=coord_text,
                x_override=x_override,
                y_override=y_override,
                font_size=font_size,
                opacity=opacity
            )

        out_folder.mkdir(parents=True, exist_ok=True)
        out_photo_path = out_folder / photo_name
        stamped_img.save(out_photo_path, "JPEG", quality=95)

        # Update or create meta.json
        meta_data = {}
        if meta_path.exists():
            try:
                with open(meta_path, "r", encoding="utf-8") as mf:
                    meta_data = json.load(mf)
            except Exception:
                meta_data = {}

        if "photos" not in meta_data:
            meta_data["photos"] = {}

        meta_data["photos"][photo_name] = {
            **meta_info,
            "manualEdit": bool(x_override is not None or y_override is not None or coord_override is not None),
            "updatedAt": meta_data.get("photos", {}).get(photo_name, {}).get("updatedAt")
        }
        meta_data["folderKey"] = f"Tim_{tim_n}/{btp}/{category}/{identifier}"
        meta_data["coordinate"] = coord_text

        with open(meta_path, "w", encoding="utf-8") as mf:
            json.dump(meta_data, mf, indent=2)

        return True
    except Exception as e:
        print(f"[ERROR] Failed to process {norm_rel}: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(description="Edit Koordinat Foto (Top-Left GPS Stamper)")
    parser.add_argument("--input", type=str, default=None, help="Path relatif atau folder aset spesifik")
    parser.add_argument("--export-dir", type=Path, default=DEFAULT_EXPORT_DIR)
    parser.add_argument("--temp-dir", type=Path, default=DEFAULT_TEMP_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--schedule", type=Path, default=DEFAULT_SCHEDULE_FILE)
    parser.add_argument("--mapping", type=Path, default=DEFAULT_MAPPING_FILE)
    parser.add_argument("--coord-override", type=str, default=None, help="Teks koordinat kustom")
    parser.add_argument("--x-override", type=int, default=None, help="Posisi X kustom")
    parser.add_argument("--y-override", type=int, default=None, help="Posisi Y kustom")
    parser.add_argument("--font-size", type=int, default=None, help="Ukuran font teks")
    parser.add_argument("--opacity", type=int, default=140, help="Transparansi latar belakang (0-255)")
    parser.add_argument("--tim-filter", type=int, default=None, help="Filter hanya Tim 1 atau Tim 2")
    parser.add_argument("--clear-output", action="store_true", help="Bersihkan folder output sebelum proses")
    args = parser.parse_args()

    export_dir = args.export_dir
    temp_dir = args.temp_dir
    output_dir = args.output_dir

    if args.clear_output and output_dir.exists():
        import shutil
        print(f"[INFO] Clearing output directory: {output_dir}")
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    schedule_data = load_schedule(args.schedule)
    schedule_lookup = build_schedule_lookup(schedule_data, tim_filter=args.tim_filter)
    mapping_data = load_mapping(args.mapping)

    photos_to_process = []
    if args.input:
        in_path = Path(args.input)
        if in_path.is_file() or in_path.suffix.lower() in [".jpg", ".jpeg"]:
            # Single file
            if in_path.is_absolute():
                try:
                    rel = in_path.relative_to(export_dir)
                except ValueError:
                    try:
                        rel = in_path.relative_to(temp_dir)
                    except ValueError:
                        parts = in_path.parts
                        if "03_photos_export" in parts:
                            idx = parts.index("03_photos_export")
                            rel = Path(*parts[idx+1:])
                        elif "03_photos_cropped_temp" in parts:
                            idx = parts.index("03_photos_cropped_temp")
                            rel = Path(*parts[idx+1:])
                        else:
                            rel = Path(parts[-4], parts[-3], parts[-2], parts[-1])
            else:
                rel = in_path
            photos_to_process.append(str(rel).replace("\\", "/"))
        elif in_path.is_dir() or not in_path.suffix:
            # Subfolder
            scan_dir = in_path if in_path.exists() else (export_dir / in_path)
            if scan_dir.exists():
                for p in scan_dir.rglob("*.jpg"):
                    try:
                        rel = p.resolve().relative_to(export_dir.resolve())
                    except ValueError:
                        try:
                            rel = p.relative_to(export_dir)
                        except ValueError:
                            rel = p.name
                    photos_to_process.append(str(rel).replace("\\", "/"))
    else:
        # Full batch scan of 03_photos_export
        if export_dir.exists():
            for p in sorted(export_dir.rglob("*.jpg")):
                try:
                    rel = p.relative_to(export_dir)
                    photos_to_process.append(str(rel).replace("\\", "/"))
                except Exception:
                    pass

    total_photos = len(photos_to_process)
    print(f"[INFO] Total photos to process for coordinates: {total_photos}")
    if total_photos == 0:
        print("[WARN] No photos found to process.")
        return 0

    success_count = 0
    fail_count = 0
    skipped_count = 0
    current_asset_folder = None
    asset_folder_count = 0

    for i, rel in enumerate(photos_to_process, 1):
        rel_path = Path(rel)
        folder_key = str(rel_path.parent).replace('\\', '/')
        if folder_key != current_asset_folder:
            if current_asset_folder is not None:
                print(f"  └── [OK] Folder selesai diproses\n", flush=True)
            current_asset_folder = folder_key
            asset_folder_count += 1
            print(f"[{asset_folder_count}] 📁 {folder_key}", flush=True)

        ok = process_single_photo(
            rel,
            export_dir=export_dir,
            temp_dir=temp_dir,
            output_dir=output_dir,
            schedule_lookup=schedule_lookup,
            mapping_data=mapping_data,
            coord_override=args.coord_override,
            x_override=args.x_override,
            y_override=args.y_override,
            font_size=args.font_size,
            opacity=args.opacity,
            forced_tim=args.tim_filter
        )
        if ok is True:
            success_count += 1
            print(f"  │   ├── {rel_path.name} -> Koordinat berhasil ditempel (04_koordinat)", flush=True)
        elif ok is None:
            skipped_count += 1
        else:
            fail_count += 1

    if current_asset_folder is not None:
        print(f"  └── [OK] Folder selesai diproses\n", flush=True)

    summary = {
        "step": "edit_photo_coordinate_only",
        "total": total_photos,
        "success": success_count,
        "skipped": skipped_count,
        "failed": fail_count
    }
    print(f"\n__SUMMARY__:{json.dumps(summary)}")
    print(f"[OK] Done. Success: {success_count}, Skipped: {skipped_count}, Failed: {fail_count}")
    return 0 if success_count > 0 or total_photos == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
