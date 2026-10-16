#!/usr/bin/env python3
"""
scripts/fast_update_timemark.py
--------------------------------
Fast re-stamp of timemark text onto photos based on schedule.json.
Uses cached coordinates (xPos, yPos) from existing meta.json in 04_photos_edited.
Avoids re-running heavy OCR, red-guide detection, or Google Vision from scratch.
Source photo: 03_photos_temp (if collage crop exists) or 03_photos_export.
Destination: 04_photos_edited/Tim_{n}/{btp}/{category}/{identifier}/{photo}
"""

import sys
import os
import time
import json
import re
import argparse
from pathlib import Path
from datetime import datetime
import numpy as np
from PIL import Image, ImageDraw

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

APP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_DIR / "scripts"))

from edit_timemark_ide1 import (
    diffuse_fill,
    draw_textbox,
    load_schedule,
    iso_to_timemark,
    normalize_schedule_identifier,
    get_font,
    BOX_HEIGHT_RATIO,
)

DEFAULT_SCHEDULE = APP_DIR / "schedule.json"
DEFAULT_EXPORT = APP_DIR / "03_photos_export"
DEFAULT_TEMP = APP_DIR / "03_photos_temp"
DEFAULT_EDITED = APP_DIR / "04_photos_edited"


def find_source_photo(btp: str, category: str, identifier: str, pname: str) -> Path | None:
    """Find clean source photo in 03_photos_temp (cropped) or 03_photos_export."""
    # 1. Check temp (cropped collage)
    p_temp = DEFAULT_TEMP / btp / category / identifier / pname
    if p_temp.exists():
        return p_temp
    
    # 2. Check export exact
    p_export = DEFAULT_EXPORT / btp / category / identifier / pname
    if p_export.exists():
        return p_export
    
    # 3. Space-insensitive fallback in 03_photos_export
    cat_dir = DEFAULT_EXPORT / btp / category
    if cat_dir.exists():
        norm_ident = identifier.replace(" ", "").upper()
        for sub in cat_dir.iterdir():
            if sub.is_dir() and sub.name.replace(" ", "").upper() == norm_ident:
                cand = sub / pname
                if cand.exists():
                    return cand
    return None


def fast_update(schedule_path: Path = DEFAULT_SCHEDULE, force: bool = False, asset_filter: str | None = None):
    start_time = time.time()
    print("=" * 60)
    print("⚡ FAST UPDATE TIMEMARK (UPDATE TEXTBOX DARI SCHEDULER)")
    print(f"Jadwal Acuan: {schedule_path}")
    print("=" * 60)

    if not schedule_path.exists():
        print(f"[ERROR] Berkas jadwal {schedule_path} tidak ditemukan!", file=sys.stderr)
        return 1

    with open(schedule_path, "r", encoding="utf-8") as f:
        s_data = json.load(f)
    schedules = s_data.get("schedules", [])
    if not schedules:
        print("[WARN] Tidak ada jadwal di schedule.json.")
        return 0

    # Build cache of existing meta.json files in 04_photos_edited
    meta_cache = {}  # (norm_ident, pname) -> dict
    for meta_file in DEFAULT_EDITED.glob("**/meta.json"):
        try:
            with open(meta_file, "r", encoding="utf-8") as mf:
                mdata = json.load(mf)
            parts = meta_file.relative_to(DEFAULT_EDITED).parts
            if len(parts) >= 4:
                # parts: ('Tim_1', 'BTP JAK', 'AXC', 'ZP 10 BOO', 'meta.json')
                folder_tim = parts[0]
                folder_btp = parts[1]
                folder_cat = parts[2]
                folder_ident = parts[3]
                for p_name, p_meta in mdata.items():
                    key = (folder_btp, folder_cat, folder_ident.replace(" ", "").upper(), p_name)
                    meta_cache[key] = {**p_meta, "_tim": folder_tim, "_meta_path": meta_file}
        except Exception:
            pass

    updated_count = 0
    skipped_count = 0
    error_count = 0
    total_photos = 0

    for sched in schedules:
        btp = sched.get("btp", "BTP JAK")
        cat = sched.get("category", "UNKNOWN")
        raw_ident = sched.get("identifier") or sched.get("pdf_stem", "")
        ident = normalize_schedule_identifier(raw_ident)
        tim_n = f"Tim_{sched.get('tim', 1)}"
        photos = sched.get("photos", {})

        if asset_filter and asset_filter.lower() not in ident.lower():
            continue

        for pname, iso_ts in photos.items():
            total_photos += 1
            try:
                target_text = iso_to_timemark(iso_ts)
            except Exception:
                continue

            target_dir = DEFAULT_EDITED / tim_n / btp / cat / ident
            dest_file = target_dir / pname
            meta_file = target_dir / "meta.json"

            norm_key = (btp, cat, ident.replace(" ", "").upper(), pname)
            cached_meta = meta_cache.get(norm_key, {})

            # Check if already up to date
            if dest_file.exists() and not force:
                cur_text = cached_meta.get("dateText", "")
                cur_tim = cached_meta.get("_tim", "")
                if cur_text == target_text and cur_tim == tim_n:
                    skipped_count += 1
                    continue

            # Need to update! Find source photo
            src_photo = find_source_photo(btp, cat, ident, pname)
            if not src_photo or not src_photo.exists():
                print(f"[SKIP] Foto sumber tidak ditemukan untuk: {ident}/{pname}")
                error_count += 1
                continue

            try:
                img = Image.open(src_photo).convert("RGB")
                w, h = img.size

                x1 = cached_meta.get("xPos", 14)
                y1 = cached_meta.get("yPos", int(h * 0.733))
                box_h = max(18, int(h * BOX_HEIGHT_RATIO))
                y2 = y1 + box_h

                font_size = max(9, min(160, int(w * 0.038)))
                font = get_font(font_size)
                dummy = ImageDraw.Draw(Image.new("L", (1, 1)))
                fit_stroke = 1 if font_size >= 28 else 0
                bbox = dummy.textbbox((0, 0), target_text, font=font, stroke_width=fit_stroke)
                tw = bbox[2] - bbox[0]
                pad_x = max(4, int(w * 0.010))
                fit_w = tw + (2 * pad_x)
                x2 = min(w, x1 + fit_w)
                box = (x1, y1, x2, y2)

                # Fast diffuse inpainting on original clean photo
                arr = np.array(img)
                crop = arr[y1:y2, x1:x2]
                mask = np.ones((y2 - y1, x2 - x1), dtype=bool)
                arr[y1:y2, x1:x2] = diffuse_fill(crop, mask, steps=25)
                img_erased = Image.fromarray(arr)

                # Draw new textbox
                img_out = draw_textbox(img_erased, box, target_text)

                # Save to destination
                target_dir.mkdir(parents=True, exist_ok=True)
                img_out.save(dest_file, quality=95, subsampling=0)

                # Clean up old location if Tim group changed
                old_tim = cached_meta.get("_tim")
                if old_tim and old_tim != tim_n:
                    old_file = DEFAULT_EDITED / old_tim / btp / cat / ident / pname
                    if old_file.exists():
                        try:
                            old_file.unlink()
                        except Exception:
                            pass

                # Update target meta.json
                folder_meta = {}
                if meta_file.exists():
                    try:
                        with open(meta_file, "r", encoding="utf-8") as mf:
                            folder_meta = json.load(mf)
                    except Exception:
                        folder_meta = {}
                
                meta_item = folder_meta.get(pname, {})
                meta_item["stage"] = cached_meta.get("stage", "stage_fast_update")
                meta_item["detector"] = cached_meta.get("detector", "cache")
                meta_item["dateText"] = target_text
                meta_item["updatedAt"] = datetime.now().isoformat()
                meta_item["xPos"] = x1
                meta_item["yPos"] = y1
                folder_meta[pname] = meta_item

                with open(meta_file, "w", encoding="utf-8") as mf:
                    json.dump(folder_meta, mf, indent=2, ensure_ascii=False)

                meta_cache[norm_key] = {**meta_item, "_tim": tim_n, "_meta_path": meta_file}
                updated_count += 1
                if updated_count % 25 == 0 or updated_count <= 5:
                    print(f"  [UPDATE] {tim_n}/{cat}/{ident}/{pname} -> {target_text}")

            except Exception as e:
                print(f"  [ERROR] Gagal memproses {ident}/{pname}: {e}")
                error_count += 1

    elapsed = time.time() - start_time
    summary = {
        "total_checked": total_photos,
        "updated": updated_count,
        "skipped": skipped_count,
        "errors": error_count,
        "elapsed_seconds": round(elapsed, 2)
    }

    print("\n" + "=" * 60)
    print(f"✅ Selesai dalam {elapsed:.2f} detik!")
    print(f"   • Total dicek: {total_photos}")
    print(f"   • Berhasil diperbarui: {updated_count}")
    print(f"   • Dilewati (sudah sesuai): {skipped_count}")
    if error_count > 0:
        print(f"   • Gagal/error: {error_count}")
    print("=" * 60)
    print(f"__SUMMARY__:{json.dumps(summary)}")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Fast Update Timemark from schedule.json")
    parser.add_argument("--schedule", type=Path, default=DEFAULT_SCHEDULE, help="Path to schedule.json")
    parser.add_argument("--force", action="store_true", help="Force re-rendering even if date matches")
    parser.add_argument("--filter", type=str, default=None, help="Filter specific asset name")
    args = parser.parse_args()

    return fast_update(args.schedule, args.force, args.filter)


if __name__ == "__main__":
    sys.exit(main())
