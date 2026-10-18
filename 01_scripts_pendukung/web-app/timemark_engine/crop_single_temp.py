import sys
import shutil
import argparse
from pathlib import Path
import numpy as np
from PIL import Image

def main():
    parser = argparse.ArgumentParser(description="Crop single collage photo for clean preview")
    parser.add_argument("--rel", required=True, help="Relative path of photo")
    parser.add_argument("--photos-dir", default="03_photos_export", help="Source photos export dir")
    parser.add_argument("--temp-dir", default="03_photos_cropped_temp", help="Temporary cropped preview dir")
    args = parser.parse_args()

    src_path = Path(args.photos_dir) / args.rel
    temp_path = Path(args.temp_dir) / args.rel

    temp_path.parent.mkdir(parents=True, exist_ok=True)

    if not src_path.exists():
        print(f"[ERROR] Source photo not found: {src_path}")
        sys.exit(1)

    try:
        from crop_collage_photos import is_collage_photo_adaptive
        from edit_timemark_ide1 import find_red_guide, find_cyan_guide_inverted

        img = Image.open(src_path)
        is_coll, div_x, div_y, reason = is_collage_photo_adaptive(img)

        if not is_coll:
            shutil.copy2(src_path, temp_path)
            print(f"[OK] Non-collage copied to temp: {temp_path}")
            return

        w, h = img.size
        quadrants = [
            ("Bottom-Left", (0, div_y, div_x, h)),
            ("Top-Left", (0, 0, div_x, div_y)),
            ("Bottom-Right", (div_x, div_y, w, h)),
            ("Top-Right", (div_x, 0, w, div_y)),
        ]
        selected_box = (0, div_y, div_x, h)
        for name, box in quadrants:
            q_img = img.convert('RGB').crop(box).resize((300, 300), Image.Resampling.LANCZOS)
            if find_red_guide(np.array(q_img), y_start=0) or find_cyan_guide_inverted(np.array(q_img)):
                selected_box = box
                break

        l, u, r, b = selected_box
        bw, bh = r - l, b - u
        side = max(1, min(bw, bh))
        cx, cy = (l + r) // 2, (u + b) // 2
        sq_l = max(0, cx - side // 2)
        sq_u = max(0, cy - side // 2)
        sq_r = min(w, sq_l + side)
        sq_b = min(h, sq_u + side)

        cropped_img = img.convert('RGB').crop((sq_l, sq_u, sq_r, sq_b))
        resized_img = cropped_img.resize((300, 300), Image.Resampling.LANCZOS)
        resized_img.save(temp_path, quality=95)
        print(f"[OK] Clean cropped collage saved to temp: {temp_path}")

    except Exception as e:
        print(f"[FALLBACK] Error cropping: {e}")
        shutil.copy2(src_path, temp_path)

if __name__ == "__main__":
    main()
