#!/usr/bin/env python3
"""
fast_update_timemark.py
-----------------------
Fast re-stamp of timemark text onto photos based on schedule.json.
Uses cached coordinates (xPos, yPos) from existing meta.json in 04_photos_edited (or 03_export_foto).
Avoids re-running heavy OCR, red-guide detection, or Google Vision from scratch.
Source photo: 03_photos_cropped_temp (if collage crop exists) or 03_export_foto / 03_photos_export.
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

ENGINE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ENGINE_DIR))

from edit_timemark_ide1 import (
    diffuse_fill,
    draw_textbox,
    load_schedule,
    iso_to_timemark,
    normalize_schedule_identifier,
    get_font,
    BOX_HEIGHT_RATIO,
)


def _strip_date_suffix(ident: str) -> str:
    return re.sub(r'_\d{2}-\d{2}(?:_part\d+)?$', '', ident.strip())


def _norm_key(text: str) -> str:
    return re.sub(r'\s+', '', text.strip().upper())


def find_source_photo(export_dir: Path, temp_dir: Path, btp: str, category: str, identifier: str, pname: str) -> Path | None:
    """Find clean source photo in 03_photos_cropped_temp (cropped) or 03_export_foto."""
    base_ident = _strip_date_suffix(identifier)
    candidates_ident = [identifier]
    if base_ident and base_ident != identifier:
        candidates_ident.append(base_ident)

    # 1. Check temp (cropped collage)
    for ident_cand in candidates_ident:
        p_temp = temp_dir / btp / category / ident_cand / pname
        if p_temp.is_file():
            return p_temp

    # 2. Check export exact
    for ident_cand in candidates_ident:
        p_export = export_dir / btp / category / ident_cand / pname
        if p_export.is_file():
            return p_export

    # 3. Space-insensitive / base-identifier fallback in temp_dir & export_dir
    for root_dir in (temp_dir, export_dir):
        cat_dir = root_dir / btp / category
        if cat_dir.is_dir():
            target_norms = {_norm_key(x) for x in candidates_ident}
            for sub in cat_dir.iterdir():
                if sub.is_dir():
                    sub_norm = _norm_key(sub.name)
                    sub_base_norm = _norm_key(_strip_date_suffix(sub.name))
                    if sub_norm in target_norms or sub_base_norm in target_norms:
                        cand = sub / pname
                        if cand.is_file():
                            return cand
    return None


def fast_update(
    schedule_path: Path,
    export_dir: Path,
    temp_dir: Path,
    edited_dir: Path,
    force: bool = False,
    asset_filter: str | None = None
) -> int:
    start_time = time.time()
    print("=" * 60, flush=True)
    print("⚡ FAST UPDATE TIMEMARK (UPDATE TEXTBOX DARI META.JSON & SCHEDULER)", flush=True)
    print(f"Jadwal Acuan    : {schedule_path}", flush=True)
    print(f"Foto Sumber (03): {export_dir}", flush=True)
    print(f"Foto Editan (04): {edited_dir}", flush=True)
    print("=" * 60, flush=True)

    if not schedule_path.is_file():
        print(f"[ERROR] Berkas jadwal {schedule_path} tidak ditemukan! Jalankan Step 3 (Scheduler) terlebih dahulu.", file=sys.stderr, flush=True)
        return 1

    with open(schedule_path, "r", encoding="utf-8") as f:
        s_data = json.load(f)
    schedules = s_data.get("schedules", [])
    if not schedules:
        print("[WARN] Tidak ada jadwal di schedule.json.", flush=True)
        return 0

    # Build cache of existing meta.json files in 04_photos_edited (and 03_export_foto if any)
    meta_cache = {}       # (btp, cat, norm_ident, pname) -> dict
    base_meta_cache = {}  # (btp, cat, norm_base_ident, pname) -> dict

    search_roots = []
    if edited_dir.is_dir():
        search_roots.append((edited_dir, True))
    if export_dir.is_dir():
        search_roots.append((export_dir, False))

    for root_dir, is_edited_root in search_roots:
        for meta_file in root_dir.glob("**/meta.json"):
            try:
                with open(meta_file, "r", encoding="utf-8") as mf:
                    mdata = json.load(mf)
                parts = meta_file.relative_to(root_dir).parts
                # Bisa ('Tim_1', 'BTP JAK', 'AXC', 'ZP 10 BOO', 'meta.json') atau ('BTP JAK', 'AXC', 'ZP 10 BOO', 'meta.json')
                if len(parts) >= 5 and parts[0].lower().startswith("tim_"):
                    folder_tim = parts[0]
                    folder_btp = parts[1]
                    folder_cat = parts[2]
                    folder_ident = parts[3]
                elif len(parts) >= 4:
                    folder_tim = ""
                    folder_btp = parts[0]
                    folder_cat = parts[1]
                    folder_ident = parts[2]
                else:
                    continue

                norm_id = _norm_key(folder_ident)
                norm_base_id = _norm_key(_strip_date_suffix(folder_ident))
                for p_name, p_meta in mdata.items():
                    if not isinstance(p_meta, dict):
                        continue
                    entry = {**p_meta, "_tim": folder_tim, "_meta_path": meta_file, "_ident": folder_ident}
                    key = (folder_btp, folder_cat, norm_id, p_name)
                    base_key = (folder_btp, folder_cat, norm_base_id, p_name)
                    if key not in meta_cache or p_meta.get("manualEdit"):
                        meta_cache[key] = entry
                    if base_key not in base_meta_cache or p_meta.get("manualEdit"):
                        base_meta_cache[base_key] = entry
            except Exception:
                pass

    print(f"[INFO] Berhasil memuat {len(meta_cache)} entri koordinat foto dari meta.json.", flush=True)

    updated_count = 0
    skipped_count = 0
    error_count = 0

    # Hitung total foto yang akan dicek untuk progress bar
    total_to_process = 0
    for sched in schedules:
        raw_ident = sched.get("identifier") or sched.get("pdf_stem", "")
        ident = normalize_schedule_identifier(raw_ident)
        if asset_filter and asset_filter.lower() not in ident.lower():
            continue
        total_to_process += len(sched.get("photos", {}))

    cur_idx = 0
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
            cur_idx += 1
            if cur_idx == 1 or cur_idx % 25 == 0 or cur_idx == total_to_process:
                print(f"[PROGRESS] {cur_idx}/{total_to_process} foto diproses...", flush=True)

            try:
                target_text = iso_to_timemark(iso_ts)
            except Exception:
                continue

            norm_key = (btp, cat, _norm_key(ident), pname)
            norm_base_key = (btp, cat, _norm_key(_strip_date_suffix(ident)), pname)
            cached_meta = meta_cache.get(norm_key) or base_meta_cache.get(norm_base_key) or {}

            target_dir = edited_dir / tim_n / btp / cat / ident
            dest_file = target_dir / pname
            meta_file = target_dir / "meta.json"

            # Check if already up to date
            if dest_file.is_file() and not force:
                cur_text = cached_meta.get("dateText", "")
                cur_tim = cached_meta.get("_tim", "")
                if cur_text == target_text and cur_tim == tim_n:
                    skipped_count += 1
                    continue

            # Find source photo
            src_photo = find_source_photo(export_dir, temp_dir, btp, cat, ident, pname)
            if not src_photo or not src_photo.is_file():
                print(f"[SKIP] Foto sumber tidak ditemukan untuk: {btp}/{cat}/{ident}/{pname}", flush=True)
                error_count += 1
                continue

            try:
                img = Image.open(src_photo).convert("RGB")
                w, h = img.size

                raw_x = cached_meta.get("xPos", 14)
                raw_y = cached_meta.get("yPos", int(h * 0.733))
                # Skalakan jika ukuran gambar bukan 300x300
                x1 = int(round((raw_x / 300.0) * w)) if (raw_x <= 300 and w > 300) else int(raw_x)
                y1 = int(round((raw_y / 300.0) * h)) if (raw_y <= 300 and h > 300) else int(raw_y)

                box_h = max(18, int(h * BOX_HEIGHT_RATIO))
                y2 = min(h, y1 + box_h)

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
                old_ident = cached_meta.get("_ident", ident)
                if old_tim and old_tim != tim_n:
                    old_file = edited_dir / old_tim / btp / cat / old_ident / pname
                    if old_file.is_file():
                        try:
                            old_file.unlink()
                        except Exception:
                            pass

                # Update target meta.json
                folder_meta = {}
                if meta_file.is_file():
                    try:
                        with open(meta_file, "r", encoding="utf-8") as mf:
                            folder_meta = json.load(mf)
                    except Exception:
                        folder_meta = {}

                meta_item = folder_meta.get(pname, {}) if isinstance(folder_meta.get(pname), dict) else {}
                meta_item["stage"] = cached_meta.get("stage", "stage_fast_update")
                meta_item["detector"] = cached_meta.get("detector", "cache")
                meta_item["dateText"] = target_text
                meta_item["updatedAt"] = datetime.now().isoformat()
                meta_item["xPos"] = raw_x
                meta_item["yPos"] = raw_y
                if cached_meta.get("manualEdit"):
                    meta_item["manualEdit"] = True
                meta_item["needCorrection"] = False
                folder_meta[pname] = meta_item

                with open(meta_file, "w", encoding="utf-8") as mf:
                    json.dump(folder_meta, mf, indent=2, ensure_ascii=False)

                meta_cache[norm_key] = {**meta_item, "_tim": tim_n, "_meta_path": meta_file, "_ident": ident}
                updated_count += 1
                if updated_count % 25 == 0 or updated_count <= 5:
                    print(f"  [UPDATE] {tim_n}/{btp}/{cat}/{ident}/{pname} -> {target_text} (x={raw_x}, y={raw_y})", flush=True)

            except Exception as e:
                print(f"  [ERROR] Gagal memproses {ident}/{pname}: {e}", flush=True)
                error_count += 1

    elapsed = time.time() - start_time
    summary = {
        "total_checked": total_to_process,
        "updated": updated_count,
        "skipped": skipped_count,
        "errors": error_count,
        "elapsed_seconds": round(elapsed, 2)
    }

    print("\n" + "=" * 60, flush=True)
    print(f"✅ Fast Update Timemark Selesai dalam {elapsed:.2f} detik!", flush=True)
    print(f"   • Total dicek        : {total_to_process}", flush=True)
    print(f"   • Berhasil diperbarui: {updated_count}", flush=True)
    print(f"   • Dilewati (sesuai)  : {skipped_count}", flush=True)
    if error_count > 0:
        print(f"   • Gagal/error        : {error_count}", flush=True)
    print("=" * 60, flush=True)
    print(f"__SUMMARY__:{json.dumps(summary)}", flush=True)
    return 0


def main():
    parser = argparse.ArgumentParser(description="Fast Update Timemark from schedule.json & meta.json")
    parser.add_argument("--schedule", type=Path, default=Path("schedule.json"), help="Path to schedule.json")
    parser.add_argument("--input", type=Path, default=Path("03_export_foto"), help="Path to 03_export_foto")
    parser.add_argument("--temp", type=Path, default=Path("03_photos_cropped_temp"), help="Path to 03_photos_cropped_temp")
    parser.add_argument("--output", type=Path, default=Path("04_photos_edited"), help="Path to 04_photos_edited")
    parser.add_argument("--force", action="store_true", help="Force re-rendering even if date matches")
    parser.add_argument("--filter", type=str, default=None, help="Filter specific asset name")
    args = parser.parse_args()

    return fast_update(args.schedule, args.input, args.temp, args.output, args.force, args.filter)


if __name__ == "__main__":
    sys.exit(main())
