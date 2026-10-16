#!/usr/bin/env python3
"""edit_photo_time_only.py — Tempel jam perawatan saja (HH:MM) di pojok kanan atas foto.

Input: 03_photos_export (atau 03_photos_cropped_temp jika foto kolase).
Jadwal: schedule.json (dari Step 3 Scheduler).
Output: 04_Time/Tim_N/{btp}/{category}/{identifier}/{photo}.jpg
"""

import os
import sys
import json
import re
import argparse
from pathlib import Path
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

DEFAULT_EXPORT_DIR = Path("03_photos_export")
DEFAULT_TEMP_DIR = Path("03_photos_cropped_temp")
DEFAULT_OUTPUT_DIR = Path("04_Time")
DEFAULT_SCHEDULE_FILE = Path("schedule.json")
DEFAULT_LOGS_DIR = Path("logs")

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
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize_schedule_identifier(identifier: str) -> str:
    return "ZP 41 BOO" if identifier.strip().upper() == "ZP 41B BOO" else identifier.strip()


def build_schedule_time_lookup(schedule_data: dict, tim_filter: int | None = None):
    """Build lookup: (btp, category, identifier, photo_stem) -> (time_str 'HH:MM', tim_n)."""
    lookup = {}
    for sched in schedule_data.get("schedules", []):
        tim_n = sched.get("tim", 1)
        if tim_filter is not None and tim_n != tim_filter:
            continue
        btp = sched.get("btp", "BTP JAK")
        category = sched.get("category", "UNKNOWN")
        identifier = normalize_schedule_identifier(sched.get("identifier") or sched.get("pdf_stem", ""))
        for pname, iso_ts in sched.get("photos", {}).items():
            try:
                dt = datetime.fromisoformat(iso_ts)
                time_str = f"{dt.hour:02d}:{dt.minute:02d}"
            except Exception:
                time_str = "07:00"

            key = (btp, category, identifier, pname)
            existing = lookup.get(key)
            if existing is None or tim_n > existing[1]:
                lookup[key] = (time_str, tim_n)
    return lookup


def read_target_date_txt(folder: Path) -> str:
    date_txt = folder / "date.txt"
    if date_txt.exists():
        try:
            return date_txt.read_text(encoding="utf-8").strip()
        except Exception:
            pass
    return "07:00"


def draw_top_right_time(
    img: Image.Image,
    time_text: str,
    x_override: int | None = None,
    y_override: int | None = None,
    font_size: int | None = None,
    opacity: int = 140,
    margin_right: int = 8,
    margin_top: int = 8,
) -> tuple[Image.Image, dict]:
    """Draws white time text in HH:MM format with semi-transparent black background."""
    w, h = img.size
    
    # Calculate font size: default ~16-18px for 300x300 image
    if font_size is None or font_size <= 0:
        font_size = max(11, min(100, int(w * 0.056)))
    font = get_font(font_size)

    # Measure text
    dummy = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    bbox = dummy.textbbox((0, 0), time_text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]

    pad_x = max(4, int(w * 0.015))
    pad_y = max(2, int(h * 0.008))
    box_w = tw + (2 * pad_x)
    box_h = th + (2 * pad_y)

    # Determine position
    if x_override is not None and y_override is not None:
        x1 = max(0, min(w - box_w, int(x_override)))
        y1 = max(0, min(h - box_h, int(y_override)))
    else:
        # Default top-right
        x1 = max(0, w - margin_right - box_w)
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
    draw.text((text_x, text_y), time_text, fill=(255, 255, 255, 255), font=font)

    meta_info = {
        "timeText": time_text,
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
    time_override: str | None = None,
    x_override: int | None = None,
    y_override: int | None = None,
    font_size: int | None = None,
    opacity: int = 140,
    forced_tim: int | None = None,
) -> bool:
    """Processes 1 photo, stamps time, saves to 04_Time/Tim_N/..."""
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

    # 2. Determine time text & tim group
    lookup_key = (btp, category, identifier, photo_name)
    alt_lookup_key = (btp, category, identifier, photo_stem)
    sched_info = schedule_lookup.get(lookup_key) or schedule_lookup.get(alt_lookup_key)

    if forced_tim is not None:
        tim_n = forced_tim
    elif sched_info:
        tim_n = sched_info[1]
    else:
        tim_n = 1

    if time_override:
        time_text = time_override.strip()
    elif sched_info:
        time_text = sched_info[0]
    else:
        # Fallback time calculation based on photo stem (0->07:00, 50->07:22, 100->07:45)
        pct = 0
        if photo_stem == "50":
            pct = 50
        elif photo_stem == "100":
            pct = 100
        duration = 45
        tot_min = 7 * 60 + round((pct * duration) / 100)
        hh = (tot_min // 60) % 24
        mm = tot_min % 60
        time_text = f"{hh:02d}:{mm:02d}"

    # 3. Open image and stamp time
    try:
        with Image.open(src_path) as orig_img:
            img = orig_img.convert("RGB")
            out_img, meta = draw_top_right_time(
                img,
                time_text,
                x_override=x_override,
                y_override=y_override,
                font_size=font_size,
                opacity=opacity
            )

        # 4. Save to destination: 04_Time/Tim_N/rel_path
        dst_folder = output_dir / f"Tim_{tim_n}" / btp / category / identifier
        dst_folder.mkdir(parents=True, exist_ok=True)
        dst_file = dst_folder / photo_name
        out_img.save(dst_file, quality=95)

        # 5. Save/Update meta.json
        meta_path = dst_folder / "meta.json"
        folder_meta = {}
        if meta_path.exists():
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    folder_meta = json.load(f)
            except Exception:
                folder_meta = {}

        meta["updatedAt"] = datetime.now().isoformat()
        folder_meta[photo_name] = meta
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(folder_meta, f, indent=2)

        return True
    except Exception as e:
        print(f"[ERROR] Failed to process {norm_rel}: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(description="Edit Photo Time Only (04_Time)")
    parser.add_argument("--schedule", default=str(DEFAULT_SCHEDULE_FILE), help="Path to schedule.json")
    parser.add_argument("--export-dir", default=str(DEFAULT_EXPORT_DIR), help="Path to 03_photos_export")
    parser.add_argument("--temp-dir", default=str(DEFAULT_TEMP_DIR), help="Path to 03_photos_cropped_temp")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Path to 04_Time")
    parser.add_argument("--input", help="Single photo relative path or subfolder path to process")
    parser.add_argument("--time-override", help="Force specific HH:MM time")
    parser.add_argument("--x-override", type=int, help="X position override (px)")
    parser.add_argument("--y-override", type=int, help="Y position override (px)")
    parser.add_argument("--font-size", type=int, help="Font size (px)")
    parser.add_argument("--opacity", type=int, default=140, help="Background opacity (0..255)")
    parser.add_argument("--tim-filter", type=int, choices=[1, 2], help="Process only Tim 1 or Tim 2")
    args = parser.parse_args()

    export_dir = Path(args.export_dir).resolve()
    temp_dir = Path(args.temp_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    schedule_file = Path(args.schedule).resolve()

    schedule_data = load_schedule(schedule_file)
    schedule_lookup = build_schedule_time_lookup(schedule_data, tim_filter=args.tim_filter)

    print(f"[INFO] Edit Photo Time Only Started...")
    print(f"[INFO] Source export: {export_dir}")
    print(f"[INFO] Target output: {output_dir}")
    print(f"[INFO] Loaded schedules: {len(schedule_data.get('schedules', []))} records ({len(schedule_lookup)} photo keys)")

    # Find list of photos to process
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
                        # Fallback parsing parts
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
    print(f"[INFO] Total photos to stamp: {total_photos}")
    if total_photos == 0:
        print("[WARN] No photos found to process.")
        return 0

    success_count = 0
    fail_count = 0
    current_asset_folder = None
    asset_folder_count = 0

    for i, rel in enumerate(photos_to_process, 1):
        rel_path = Path(rel)
        folder_key = str(rel_path.parent).replace('\\', '/')
        if folder_key != current_asset_folder:
            if current_asset_folder is not None:
                print(f"  └── [OK] Folder selesai distamp\n", flush=True)
            current_asset_folder = folder_key
            asset_folder_count += 1
            print(f"[{asset_folder_count}] 📁 {folder_key}", flush=True)

        ok = process_single_photo(
            rel,
            export_dir=export_dir,
            temp_dir=temp_dir,
            output_dir=output_dir,
            schedule_lookup=schedule_lookup,
            time_override=args.time_override,
            x_override=args.x_override,
            y_override=args.y_override,
            font_size=args.font_size,
            opacity=args.opacity,
            forced_tim=args.tim_filter
        )
        if ok:
            success_count += 1
            print(f"  │   ├── {rel_path.name} -> Jam foto berhasil ditempel (04_Time)", flush=True)
        else:
            fail_count += 1
            print(f"  │   ├── ❌ [ERROR] {rel_path.name} gagal distamp", flush=True)

    if current_asset_folder is not None:
        print(f"  └── [OK] Folder selesai distamp\n", flush=True)

    summary = {
        "step": "edit_photo_time_only",
        "total": total_photos,
        "success": success_count,
        "failed": fail_count
    }
    print(f"\n__SUMMARY__:{json.dumps(summary)}")
    print(f"[OK] Done. Success: {success_count}, Failed: {fail_count}")
    return 0 if success_count > 0 or total_photos == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
