import argparse
import os
import sys
import shutil
from pathlib import Path
from PIL import Image

def crop_photo_custom(photo_path: Path, quadrant: str = None, crop_box: tuple = None, photos_dir: str = "03_photos_export", temp_dir: str = "03_photos_cropped_temp"):
    if not photo_path.exists():
        print(f"[SKIP] File not found: {photo_path}")
        return False
        
    try:
        # Robust relative path determination
        photo_path = photo_path.resolve()
        parts = photo_path.parts
        if "03_photos_export" in parts:
            idx = parts.index("03_photos_export")
            rel = Path(*parts[idx+1:])
        else:
            try:
                rel = photo_path.relative_to(Path(photos_dir).resolve())
            except ValueError:
                rel = Path(photo_path.name)

        out_temp_path = Path(temp_dir) / rel
        out_temp_path.parent.mkdir(parents=True, exist_ok=True)

        img = Image.open(photo_path).convert("RGB")
        w, h = img.size
        
        if crop_box and len(crop_box) == 4:
            norm_l, norm_t, norm_r, norm_b = crop_box
            left = max(0, int(round((norm_l / 100.0) * w)))
            upper = max(0, int(round((norm_t / 100.0) * h)))
            right = min(w, int(round((norm_r / 100.0) * w)))
            lower = min(h, int(round((norm_b / 100.0) * h)))
            if right <= left or lower <= upper:
                print(f"[ERROR] Invalid crop box dimensions: {crop_box}")
                return False
            box = (left, upper, right, lower)
        else:
            mid_x, mid_y = w // 2, h // 2
            if quadrant == 'top-left':
                box = (0, 0, mid_x, mid_y)
            elif quadrant == 'top-right':
                box = (mid_x, 0, w, mid_y)
            elif quadrant == 'bottom-right':
                box = (mid_x, mid_y, w, h)
            else: # bottom-left (default)
                box = (0, mid_y, mid_x, h)

        cropped = img.crop(box)
        resized = cropped.resize((300, 300), Image.Resampling.LANCZOS)
        resized.save(out_temp_path, quality=95)
        print(f"[CROP SUCCESS] {rel} -> Saved clean crop to temp: {out_temp_path}")
        return True
    except Exception as e:
        print(f"[ERROR] {photo_path.name}: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Manual Photo Quadrant & Custom Box Crop Helper")
    parser.add_argument("--quadrant", default="bottom-left", choices=["bottom-left", "bottom-right", "top-left", "top-right"])
    parser.add_argument("--crop-box", nargs=4, type=float, help="Custom crop box percentages: left upper right lower (0..100)")
    parser.add_argument("--files", nargs="+", required=True)
    parser.add_argument("--photos-dir", default="03_photos_export")
    parser.add_argument("--temp-dir", default="03_photos_cropped_temp")
    args = parser.parse_args()

    crop_box = tuple(args.crop_box) if args.crop_box else None
    for fpath in args.files:
        crop_photo_custom(Path(fpath), args.quadrant, crop_box, args.photos_dir, args.temp_dir)

if __name__ == "__main__":
    main()
