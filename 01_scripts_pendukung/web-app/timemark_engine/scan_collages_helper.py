"""
scan_collages_helper.py — Collage Analyzer backend helper.
- Scans 03_photos_export for 2x2 collage photos using white border detection
- Returns JSON list of detected collages with crop box preview
- Also handles --save-crops mode to apply confirmed crops
"""
import os
import sys
import json
import shutil
import base64
import argparse
from pathlib import Path
from io import BytesIO

import numpy as np
from PIL import Image

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Import from crop_collage_photos.py
sys.path.insert(0, str(Path(__file__).parent))
from crop_collage_photos import detect_collage_by_crosshair, get_crop_box_bottom_left, is_collage_photo_adaptive


def pil_to_base64(img: Image.Image, max_size: int = 300) -> str:
    """Resize and convert PIL image to base64 JPEG string."""
    img = img.copy()
    img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
    buf = BytesIO()
    img.convert('RGB').save(buf, format='JPEG', quality=80)
    return base64.b64encode(buf.getvalue()).decode('utf-8')


def scan_collages(photos_dir: str) -> list[dict]:
    """Scan photos_dir for collage photos. Returns list of detected entries."""
    root = Path(photos_dir)
    matches = []
    results = []

    for p in sorted(root.glob("**/*.jpg")):
        try:
            img = Image.open(p)
            is_coll, div_x, div_y, reason = is_collage_photo_adaptive(img)

            if not is_coll:
                continue

            rel = str(p.relative_to(root)).replace('\\', '/')
            crop_box = list(get_crop_box_bottom_left(img))  # [left, upper, right, lower]

            results.append({
                'rel': rel,
                'rawUrl': f"/static/photos/export/{rel}",
                'size': list(img.size),          # [w, h]
                'cropBox': crop_box,              # [left, upper, right, lower] pixels
                'cropBoxPct': [                   # percentages for frontend display
                    round(crop_box[0] / img.size[0] * 100, 1),
                    round(crop_box[1] / img.size[1] * 100, 1),
                    round(crop_box[2] / img.size[0] * 100, 1),
                    round(crop_box[3] / img.size[1] * 100, 1),
                ],
                'reason': reason,
            })
            print(f"  [COLLAGE] {rel} ({img.size[0]}x{img.size[1]}) - {reason}")
        except Exception as e:
            print(f"  [ERROR] {p}: {e}", file=sys.stderr)

    return results


def _clear_edited_copies(rel: str, photos_dir: str):
    """Delete edited copies from 04_photos_edited/Tim_*/ so gallery shows as UNEDITED."""
    # 04_photos_edited is a sibling of 03_photos_export
    export_root = Path(photos_dir)
    edited_root = export_root.parent / '04_photos_edited'
    if not edited_root.exists():
        return
    # rel is like "BTP BD/PTDS/MSG/0.jpg" — strip filename to get folder
    rel_folder = str(Path(rel).parent).replace('\\', '/')
    filename = Path(rel).name
    for tim_dir in edited_root.iterdir():
        if not tim_dir.is_dir():
            continue
        target = tim_dir / rel_folder / filename
        if target.exists():
            try:
                target.unlink()
                print(f"  [CLEARED EDITED] {target}")
            except Exception as e:
                print(f"  [WARN] Could not delete {target}: {e}", file=sys.stderr)


def save_crops(crops: list[dict], photos_dir: str, logs_dir: str = 'logs'):
    """Apply crops to photos in photos_dir. Backup originals to logs/collage_originals/.
    Also clears old edited copies from 04_photos_edited so gallery shows them as UNEDITED.
    """
    root = Path(photos_dir)
    backup_root = Path(logs_dir) / 'collage_originals'
    backup_root.mkdir(parents=True, exist_ok=True)

    manifest_path = Path(logs_dir) / 'cropped_collages.json'
    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
    except Exception:
        manifest = []

    saved = 0
    for entry in crops:
        rel = entry['rel']
        crop_box = entry['cropBox']  # [left, upper, right, lower] in pixels
        src = root / rel
        if not src.exists():
            print(f"  [SKIP] Not found: {src}", file=sys.stderr)
            continue
        try:
            img = Image.open(src).convert('RGB')
            # Backup original (only if no backup exists yet)
            bk = backup_root / rel
            bk.parent.mkdir(parents=True, exist_ok=True)
            if not bk.exists():
                shutil.copy2(src, bk)

            # Crop, enforce 1:1 square ratio, and resize to 300x300
            l, u, r, b = crop_box
            bw, bh = r - l, b - u
            side = max(1, min(bw, bh))
            cx, cy = (l + r) // 2, (u + b) // 2
            sq_l = max(0, cx - side // 2)
            sq_u = max(0, cy - side // 2)
            sq_r = min(img.size[0], sq_l + side)
            sq_b = min(img.size[1], sq_u + side)
            square_box = (sq_l, sq_u, sq_r, sq_b)

            cropped = img.crop(square_box)
            resized = cropped.resize((300, 300), Image.Resampling.LANCZOS)
            resized.save(src, quality=95)
            print(f"  [CROPPED] {rel} → box={square_box} (Resized 300x300)")

            # Clear old edited copies so gallery shows as UNEDITED
            _clear_edited_copies(rel, str(root))

            # Add to manifest
            if rel not in manifest:
                manifest.append(rel)
            saved += 1
        except Exception as e:
            print(f"  [ERROR] {rel}: {e}", file=sys.stderr)

    # Write updated manifest
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)

    print(f"\n[OK] {saved}/{len(crops)} photos cropped. Manifest updated: {manifest_path}")
    return saved


def restore_crop(rel: str, photos_dir: str, logs_dir: str = 'logs') -> bool:
    """Restore a previously cropped photo back to its original collage state from backup."""
    root = Path(photos_dir)
    backup_root = Path(logs_dir) / 'collage_originals'
    bk = backup_root / rel
    dst = root / rel

    if not bk.exists():
        print(f"  [ERROR] No backup found: {bk}", file=sys.stderr)
        return False

    shutil.copy2(bk, dst)
    print(f"  [RESTORED] {rel} ← {bk}")

    # Also clear edited copies so gallery shows as UNEDITED
    _clear_edited_copies(rel, str(root))

    # Remove from manifest
    manifest_path = Path(logs_dir) / 'cropped_collages.json'
    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
        manifest = [m for m in manifest if m != rel]
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2)
    except Exception:
        pass

    return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Collage Scanner & Crop Helper')
    parser.add_argument('--photos-dir', default='03_photos_export', help='Path to 03_photos_export')
    parser.add_argument('--logs-dir', default='logs', help='Path to logs dir')
    parser.add_argument('--output', choices=['json', 'text'], default='text')
    parser.add_argument('--save-crops', action='store_true', help='Apply crops instead of scanning')
    parser.add_argument('--crops-json', type=str, help='JSON string of crops list when using --save-crops')
    parser.add_argument('--restore', action='store_true', help='Restore a cropped photo from backup')
    parser.add_argument('--restore-rel', type=str, help='Relative path to restore (e.g. BTP BD/PTDS/MSG/0.jpg)')
    args = parser.parse_args()

    if args.save_crops:
        crops = json.loads(args.crops_json)
        save_crops(crops, args.photos_dir, args.logs_dir)
    elif args.restore:
        ok = restore_crop(args.restore_rel, args.photos_dir, args.logs_dir)
        print('__RESTORE_OK__' if ok else '__RESTORE_FAIL__')
    else:
        print(f"Scanning: {args.photos_dir}", flush=True)
        results = scan_collages(args.photos_dir)
        print(f"\nTotal collages detected: {len(results)}", flush=True)
        print(f"__COLLAGES__{json.dumps(results)}")
