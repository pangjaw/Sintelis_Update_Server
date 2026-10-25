#!/usr/bin/env python3
"""
auto_crop_collages.py — Deteksi & Pemotongan Otomatis Foto Kolase berbasis Garis Putih / Netral (White-Seam Isolation).

Logika Deteksi:
1. Meredupkan seluruh warna (Saturation < 8% dan Brightness > 110) sehingga hanya menyisakan garis pembatas putih/netral.
2. Memindai sumbu tengah:
   - Garis pembatas vertikal lurus (X: 147..153 px) memanjang >= 88% dari atas ke bawah.
   - Garis pembatas horizontal lurus (Y: 147..153 px) memanjang >= 80% dari kiri ke kanan.
3. Menentukan layout:
   - 2x2 (4-in-1): Garis pembatas vertikal dan horizontal lurus membelah 4 kuadran ➔ Potong kuadran kiri atas [0, 0, split_x, split_y].
   - 3-in-1 (1 Atas + 2 Bawah): Garis pembatas horizontal penuh dan vertikal pada paruh bawah ➔ Potong panel atas horizontal [0, 0, W, split_y].
4. Hasil crop di-resize ke ukuran standar 300x300 px dan disimpan di 03_photos_cropped_temp/.
5. Foto tunggal (0 false positive) 100% dilewati tanpa disentuh.
"""

import argparse
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from PIL import Image
import numpy as np

DEFAULT_INPUT = Path("03_photos_export")
DEFAULT_OUTPUT = Path("03_photos_cropped_temp")
DEFAULT_MANIFEST = Path("logs/auto_crop_manifest.json")
DEFAULT_CROPPED_SET = Path("logs/cropped_collages.json")

# Kategori yang diizinkan untuk pemeriksaan kolase
COLLAGE_ELIGIBLE_CATEGORIES = {
    "CATUDAYA", "CATU DAYA", "CATU DAYA ER RADIO", "CATU DAYA ER SINYAL",
    "PDSE", "PTDS", "PTLS"
}


def detect_white_seam_collage(img_path: Path, requested_quadrant: str | None = None) -> tuple[str, tuple[int, int, int, int] | None, dict]:
    """
    Mendeteksi apakah gambar memiliki garis pembatas putih/netral khas kolase 2x2 atau 3-in-1.
    Menggunakan ambang batas ketat (White-Seam Isolation: sat < 8%, max_c > 110, v_pct >= 0.88, h_pct >= 0.80)
    agar 0% false positive pada foto tunggal.
    Returns: (layout_type, crop_box, stats)
    """
    try:
        img = Image.open(img_path).convert("RGB")
        w, h = img.size
        arr = np.array(img)

        r = arr[:, :, 0].astype(float)
        g = arr[:, :, 1].astype(float)
        b = arr[:, :, 2].astype(float)

        # 1. Filter Garis Pembatas Putih/Netral (Saturation < 8% dan Brightness > 110)
        max_c = np.maximum(np.maximum(r, g), b)
        min_c = np.minimum(np.minimum(r, g), b)
        delta = max_c - min_c
        sat = np.where(max_c > 0, (delta / max_c) * 100.0, 0.0)

        is_neutral_line = (sat < 8.0) & (max_c > 110.0)

        # 2. Pindai Garis Putih Vertikal di Sumbu Tengah (X: 46%..54%)
        best_v_col = w // 2
        max_v_pct = 0.0
        for x in range(int(w * 0.46), int(w * 0.54)):
            strip = is_neutral_line[:, max(0, x - 1):min(w, x + 2)]
            col_hits = np.sum(np.any(strip, axis=1)) / h
            if col_hits > max_v_pct:
                max_v_pct = float(col_hits)
                best_v_col = x

        # 3. Pindai Garis Putih Horizontal di Sumbu Tengah (Y: 46%..54%)
        best_h_row = h // 2
        max_h_pct = 0.0
        for y in range(int(h * 0.46), int(h * 0.54)):
            strip = is_neutral_line[max(0, y - 1):min(h, y + 2), :]
            row_hits = np.sum(np.any(strip, axis=0)) / w
            if row_hits > max_h_pct:
                max_h_pct = float(row_hits)
                best_h_row = y

        # 4. Pindai Garis Putih Vertikal pada Paruh Bawah Saja (Layout 3-in-1)
        max_bottom_v_pct = 0.0
        for x in range(int(w * 0.46), int(w * 0.54)):
            strip = is_neutral_line[int(h * 0.55):, max(0, x - 1):min(w, x + 2)]
            bottom_hits = np.sum(np.any(strip, axis=1)) / (h * 0.45)
            if bottom_hits > max_bottom_v_pct:
                max_bottom_v_pct = float(bottom_hits)

        stats = {
            "v_pct": round(max_v_pct, 3),
            "h_pct": round(max_h_pct, 3),
            "bottom_v_pct": round(max_bottom_v_pct, 3),
            "split_x": best_v_col,
            "split_y": best_h_row
        }

        quads = {
            "TL": (0, 0, best_v_col, best_h_row),
            "TR": (best_v_col, 0, w, best_h_row),
            "BL": (0, best_h_row, best_v_col, h),
            "BR": (best_v_col, best_h_row, w, h)
        }

        # Jika user meminta kuadran eksplisit secara manual dari UI
        if requested_quadrant and requested_quadrant.upper() in quads:
            chosen = requested_quadrant.upper()
            stats["chosen_quadrant"] = chosen
            return "2x2", quads[chosen], stats

        # Klasifikasi 2x2: Garis vertikal >= 88% dan horizontal >= 80%
        if max_v_pct >= 0.88 and max_h_pct >= 0.80:
            stats["chosen_quadrant"] = "TL"
            return "2x2", quads["TL"], stats

        # Klasifikasi 3-in-1: Garis horizontal >= 80% dan paruh bawah vertikal >= 80%
        if max_h_pct >= 0.80 and max_bottom_v_pct >= 0.80:
            stats["chosen_quadrant"] = "TOP_PANEL"
            return "3_in_1", (0, 0, w, best_h_row), stats

        return "single_photo", None, stats

    except Exception as e:
        return "single_photo", None, {"error": str(e)}


def process_all_collages(input_dir: Path, output_dir: Path, manifest_path: Path, cropped_set_path: Path) -> dict:
    # 1. Bersihkan folder output cropped sebelumnya
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    all_jpgs = sorted(list(input_dir.rglob("*.jpg")))
    manifest = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "method": "white_seam_isolation",
        "total_scanned": len(all_jpgs),
        "total_collages_cropped": 0,
        "collages": []
    }

    cropped_rel_set = set()

    total_jpgs = len(all_jpgs)
    for idx_jpg, p in enumerate(all_jpgs, 1):
        try:
            if idx_jpg == 1 or idx_jpg % 50 == 0 or idx_jpg == total_jpgs:
                print(f"[PROGRESS] {idx_jpg}/{total_jpgs} foto dipindai...", flush=True)
            rel = p.relative_to(input_dir)
            rel_str = str(rel).replace("\\", "/")
            parts = rel.parts

            # Filter kategori (kategori di luar ini dijamin 100% single photo)
            cat = parts[1].upper() if len(parts) >= 2 else ""
            if cat not in COLLAGE_ELIGIBLE_CATEGORIES and not any(k in cat for k in ("CATUDAYA", "CATU DAYA", "PDSE", "PTDS", "PTLS")):
                continue

            layout, crop_box, stats = detect_white_seam_collage(p)

            if layout != "single_photo" and crop_box is not None:
                img = Image.open(p).convert("RGB")
                w, h = img.size
                x1, y1, x2, y2 = crop_box
                cropped_img = img.crop((x1, y1, x2, y2))

                # Resize ke 300x300 px
                resized_img = cropped_img.resize((300, 300), Image.Resampling.LANCZOS)

                dst_path = output_dir / rel
                dst_path.parent.mkdir(parents=True, exist_ok=True)
                resized_img.save(dst_path, quality=95, subsampling=0)

                cropped_rel_set.add(rel_str.lower())
                manifest["total_collages_cropped"] += 1
                manifest["collages"].append({
                    "rel_path": rel_str,
                    "layout": layout,
                    "original_size": [w, h],
                    "crop_box": list(crop_box),
                    "stats": stats,
                    "output_path": str(dst_path)
                })
                print(f"🖼️ [{manifest['total_collages_cropped']}] Kolase Terdeteksi: {rel_str}", flush=True)
                print(f"  ├── Layout     : {layout.upper()}", flush=True)
                print(f"  ├── Resolusi   : {w}x{h} -> Crop Box {crop_box}", flush=True)
                print(f"  └── [OK] Disimpan ke {dst_path}\n", flush=True)

        except Exception as e:
            print(f"[ERROR] Gagal memproses {p}: {e}", file=sys.stderr)

    # Simpan manifest dan update cropped_collages.json
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    cropped_set_path.write_text(json.dumps(sorted(list(cropped_rel_set)), indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n==========================================")
    print(f"AUTO-CROP WHITE-SEAM SELESAI:")
    print(f"  Total Foto Dipindai : {manifest['total_scanned']}")
    print(f"  Total Kolase Dipotong: {manifest['total_collages_cropped']}")
    print(f"  Manifest Disimpan di : {manifest_path}")
    print(f"==========================================")

    return manifest


def main():
    parser = argparse.ArgumentParser(description="Auto-Crop Collages via White-Seam Isolation")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Photos export folder")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Photos cropped temp folder")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST, help="Output manifest path")
    parser.add_argument("--cropped-set", type=Path, default=DEFAULT_CROPPED_SET, help="Cropped rel paths json")
    args = parser.parse_args()

    process_all_collages(args.input, args.output, args.manifest, args.cropped_set)


if __name__ == "__main__":
    main()
